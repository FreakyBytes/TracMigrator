#!/usr/bin/python3
"""
main script for converting trac to github
"""

import yaml
import requests
import argparse
import logging

import wiki
import trac

log = logging.getLogger('TracMigrator')

def load_config(path):
    config = {
        'github': {
            'key': None,
            'default_namespace': None
        },
        'trac': {
            'base_url': None,
            'timeout': 15,
            'user': None,
            'password': None,
        },
        'environments': {},
    }
    
    try:
        with open(path, 'r') as fs:
            config.update(yaml.safe_load(fs))
    except:
        log.warn('Failed loading config {path}. Using default values'.format(path=path))

    return config


def save_config(path, config):
    with open(path, 'w') as fs:
        yaml.dump(config, encoding=None, stream=fs)


if __name__ == '__main__':
    # main entry
    main_parser = argparse.ArgumentParser()
    main_parser.add_argument('command', choices=('get-envs', 'migrate', 'save-config'))
    main_parser.add_argument('-c', '--config', help='path to the config file', default='config.yml')
    args = main_parser.parse_args()
    # loads config
    config = load_config(args.config)

    # determine, which action to take
    if args.command == 'save-config':
        # just save the config as it is.
        # good to generate a empty dummy config
        save_config(args.config, config)

    elif args.command == 'get-envs':
        # get available envs and store them in the config
        envs_parser = argparse.ArgumentParser(parents=(main_parser,))
        envs_parser.add_argument('--override', help='overrides existing environments in the config', default=False, action='store_true')



    elif args.command == 'migrate':
        pass
