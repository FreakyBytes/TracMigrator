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
        'environments': [],
    }
    
    try:
        with open(path, 'r') as fs:
            config.update(yaml.safe_load(fs))
    except:
        log.warn('Failed loading config {path}. Using default values'.format(path=path))

    return config


def save_config(path, config):
    with open(path, 'w') as fs:
        yaml.dump(
                config,
                encoding=None,
                stream=fs,
                default_style=None,
                default_flow_style=False,
            )


if __name__ == '__main__':
    # main entry
    main_parser = argparse.ArgumentParser(conflict_handler='resolve')
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
        envs_parser = argparse.ArgumentParser(parents=(main_parser,), conflict_handler='resolve')
        envs_parser.add_argument('--override', help='overrides existing environments in the config', default=False, action='store_true')
        args = envs_parser.parse_args()
        
        env_map = {}
        if args.override is True:
            # remove old environments from config
            config['environments'] = []
        else:
            # create mapping from env trac_ids to list indexies
            for index, env in enumerate(config['environments']):
                if env['trac_id']:
                    env_map[env['trac_id']] = index
            
        for env in  trac.listTracEnvironments(config['trac']['base_url'], timeout=config['trac']['timeout']):
            log.info('Found Trac environment {id}'.format(id=env['trac_id']))
            if env['trac_id'] in env_map:
                continue

            config['environments'].append(env)
        
        save_config(args.config, config)
    elif args.command == 'migrate':
        pass
