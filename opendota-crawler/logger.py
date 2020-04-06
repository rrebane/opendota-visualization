import logging

def create_logger(name, level=logging.DEBUG, formatter=logging.Formatter(),
                  handlers=[logging.StreamHandler()]):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
