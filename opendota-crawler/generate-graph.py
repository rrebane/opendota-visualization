#!/usr/bin/env python

from __future__ import print_function
import argparse
import hashlib
import json
import logging
import pickle
import swagger_client
import time
from datetime import datetime
from ratelimit import limits, sleep_and_retry
from swagger_client.rest import ApiException
from pprint import pprint

import logger
from api_key import API_KEY
from cache import FileCache
from counter import Counter

LOGGER = logger.create_logger(__name__, level=logging.DEBUG)
CACHE = FileCache(cache_root="cache", logger=LOGGER)
REQUEST_COUNTER = Counter(counter_path="request-counter.txt", logger=LOGGER)

API_CLIENT_CONFIGURATION = swagger_client.Configuration()
API_CLIENT_CONFIGURATION.api_key = {'api_key': API_KEY}
API_CLIENT = swagger_client.ApiClient(configuration=API_CLIENT_CONFIGURATION)
MATCHES_API = swagger_client.MatchesApi(api_client=API_CLIENT)
PLAYERS_API = swagger_client.PlayersApi(api_client=API_CLIENT)

def counted_request(request, *args, **kwargs):
    try:
        response = request(*args, **kwargs)
        REQUEST_COUNTER.increment()
        return response
    except ApiException as e:
        # 5XX responses do not increment request count
        if e.status < 500 and e.status >= 600:
            REQUEST_COUNTER.increment()
        raise e

# Rate limit: 1200 calls per minute
@sleep_and_retry
@limits(calls=20, period=1)
def rate_limit_request(request, *args, **kwargs):
    # This function needs to return for rate limiting to work
    try:
        return counted_request(request, *args, **kwargs)
    except ApiException as e:
        return e

def cached_request(request, *args, **kwargs):
    name = request.__name__
    sha256 = hashlib.sha256()
    sha256.update(pickle.dumps(args))
    sha256.update(pickle.dumps(kwargs))
    cache_key = "{}-{}".format(name, sha256.hexdigest())

    if cache_key in CACHE:
        return CACHE.read(cache_key)
    else:
        response = rate_limit_request(request, *args, **kwargs)
        if isinstance(response, ApiException):
            raise response
        CACHE.write(cache_key, response)
        return response

def log_match(match):
    LOGGER.debug("Match ID: {}, Start: {}".format(match['match_id'],
                                                  datetime.fromtimestamp(match['start_time'])))

def log_player_matches(account_id, player_matches):
    LOGGER.debug("Player ID: {}, Matches: {}".format(account_id, len(player_matches)))

def log_player(player):
    mmr_estimate = player.get('mmr_estimate', {}).get('estimate', "Unknown")
    profile = player['profile']
    LOGGER.debug(
        "Player ID: {}, Name: {}, MMR estimate: {}".format(
            profile.get('account_id', "Anonymous"),
            profile.get('personaname', "Anonymous"),
            mmr_estimate))

def create_link(source, target):
    return {'source': source, 'target': target, 'match_count': 1}

def link_key(first_account_id, second_account_id):
    if first_account_id <= second_account_id:
        return (first_account_id, second_account_id)
    else:
        return (second_account_id, first_account_id)

def generate_graph(players, player_matches, matches):
    player_match_count = {}
    player_match_skill = {}

    in_same_match_count = {}
    in_same_team_count = {}
    in_opposite_team_count = {}

    for account_id, player in players.items():
        LOGGER.info("Processing player ID: {}".format(account_id))
        player_match_count[account_id] = 0
        player_match_skill[account_id] = {None: 0, 1: 0, 2: 0, 3: 0}

    for match in player_matches:
        match_id = match['match_id']
        match_skill = match['skill']

        match_full = matches[match_id]
        match_players = match_full['players']

        for match_player in match_players:
            match_player_account_id = match_player.get('account_id', None)
            if match_player_account_id:
                player_match_skill[match_player_account_id][match_skill] += 1

    for match_id, match in matches.items():
        match_players = [player for player in match['players'] if 'account_id' in player and player['account_id']]
        for i, match_player in enumerate(match_players):
            account_id = match_player['account_id']
            if account_id in player_match_count:
                player_match_count[account_id] += 1

            is_radiant = match_player['isRadiant']

            for j in range(i + 1, len(match_players)):
                other_player = match_players[j]
                other_account_id = other_player['account_id']

                other_is_radiant = other_player['isRadiant']

                key = link_key(account_id, other_account_id)
                if key in in_same_match_count:
                    in_same_match_count[key] += 1
                else:
                    in_same_match_count[key] = 1

                if is_radiant == other_is_radiant:
                    if key in in_same_team_count:
                        in_same_team_count[key] += 1
                    else:
                        in_same_team_count[key] = 1
                else:
                    if key in in_opposite_team_count:
                        in_opposite_team_count[key] += 1
                    else:
                        in_opposite_team_count[key] = 1

    nodes = []
    links = []

    for account_id, count in player_match_count.items():
        if count < 2:
            continue
        player = players[account_id]
        profile = player['profile']
        name = profile.get('personaname', "Anonymous")
        mmr_estimate = player.get('mmr_estimate', {}).get('estimate', "Unknown")
        match_skill = player_match_skill[account_id]

        nodes.append({
            'account_id': account_id,
            'name': name,
            'mmr_estimate': mmr_estimate,
            'match_count': count,
            'normal_skill_count': match_skill[1],
            'high_skill_count': match_skill[2],
            'very_high_skill_count': match_skill[3],
            'unknown_skill_count': match_skill[None]
        })

    for key, count in in_same_match_count.items():
        if player_match_count[key[0]] < 2 or player_match_count[key[1]] < 2:
            continue
        same_team_count = in_same_team_count.get(key, 0)
        opposite_team_count = in_opposite_team_count.get(key, 0)
        links.append({
            'source': key[0],
            'target': key[1],
            'match_count': count,
            'same_team_count': same_team_count,
            'opposite_team_count': opposite_team_count
        })

    LOGGER.info("Final node count: {}".format(len(nodes)))
    LOGGER.info("Final link count: {}".format(len(links)))

    return {'nodes': nodes, 'links': links}

def get_player(account_id):
    try:
        return cached_request(PLAYERS_API.players_account_id_get, account_id)
    except ApiException as e:
        if e.status == 404:
            LOGGER.warning("{}".format(e))
            return e
        raise e

def get_matches(account_id):
    try:
        return cached_request(PLAYERS_API.players_account_id_matches_get, account_id)
    except ApiException as e:
        if e.status == 404:
            LOGGER.warning("{}".format(e))
            return e
        raise e

def get_match(match_id):
    try:
        return cached_request(MATCHES_API.matches_match_id_get, match_id)
    except ApiException as e:
        if e.status == 404:
            LOGGER.warning("{}".format(e))
            return e
        raise e

def main():
    parser = argparse.ArgumentParser(description='Opendota match information')
    parser.add_argument('--account_id', type=int, required=True, help='Steam account ID')
    parser.add_argument('--output', type=str, required=True, help='Output file path')
    args = parser.parse_args()

    account_id = args.account_id
    output_path = args.output

    players = {}
    players_matches = {}
    matches = {}

    try:
        player_account = get_player(account_id)
        players[account_id] = player_account

        player_matches = get_matches(account_id)
        log_player_matches(account_id, player_matches)

        for i, match in enumerate(player_matches):
            match_id = match['match_id']
            match_full = get_match(match_id)
            if isinstance(match_full, ApiException):
                continue
            log_match(match)
            matches[match_id] = match_full
            match_players = match_full['players']

            for j, match_player in enumerate(match_players):
                match_player_account_id = match_player.get('account_id', None)
                if match_player_account_id:
                    match_player_account = get_player(match_player_account_id)
                    if isinstance(match_player_account, ApiException):
                        continue
                    log_player(match_player_account)
                    if not match_player_account_id in players:
                        players[match_player_account_id] = match_player_account

        players_matches[account_id] = player_matches

        LOGGER.info("Got {} non-anonymous players".format(len(players)))
        LOGGER.info("Got {} significant matches".format(len(matches)))

        graph = generate_graph(players, player_matches, matches)

        with open(output_path, 'w') as output_file:
            json.dump(graph, output_file)

        LOGGER.info("Output written to: {}".format(output_path))
    except ApiException as e:
        LOGGER.error("Exception: {}".format(e))

if __name__ == "__main__":
    main()
