# opendota-visualization

## Setup

### macOS

```
# Install swagger-codegen
brew cask install homebrew/cask-versions/adoptopenjdk8
brew install swagger-codegen

# Download Swagger specification for OpenDota
curl -o build/opendota-api-spec.json https://api.opendota.com/api

# Generate API code from Swagger specification
swagger-codegen generate -i https://api.opendota.com/api -l python -o opendota-python -c swagger-codegen-config.json

# Patch authentication
find opendota-python -name "*.py" | xargs -L 1 sed -i bak -e "s/auth_settings = \[\]/auth_settings = ['api_key']/"

# Create virtualenv sandbox
pip3 install virtualenv
virtualenv env
source env/bin/activate

# Install dependencies in the sandbox
pip install ratelimit
pip install ./opendota-python

# Create directory to cache OpenDota requests
mkdir cache

# Generate graph
./opendota-crawler/generate-graph.py --account_id 83588045 --output docs/graph.json
```
