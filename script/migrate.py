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

def do_save_config(args):
    """
    Just takes the loaded config and saves it again.
    Good for generating a empty config template
    """
    save_config(args.config, config)


def do_get_envs(args):
    # get available envs and store them in the config

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


def do_migrate(args):
    pass


if __name__ == '__main__':
    # main argument parser
    parser = argparse.ArgumentParser(conflict_handler='resolve')
    parser.add_argument('-c', '--config', help='path to the config file', default='config.yml')
    subparsers = parser.add_subparsers()

    # save-config
    save_config_parser = subparsers.add_parser('save-config', help="loads the config, if possible and saves it immidiatly. Good to generate empty config templates")
    save_config_parser.set_defaults(func=do_save_config)

    # get-envs
    env_parser = subparsers.add_parser('get-envs', help="gets the list of all available Trac environments from the Trac base url.")
    env_parser.add_argument('--override', help='overrides existing environments in the config', default=False, action='store_true')
    env_parser.set_defaults(func=do_get_envs)

    # migrate
    migrate_parser = subparsers.add_parser('migrate', help="migrates the Trac repositories")
    migrate_parser.add_argument('--dry-run', help='does not push anything to GitHub', default=False, action='store_true')
    migrate_parser.set_defaults(func=do_migrate)

    # parse it...
    args = parser.parse_args()
    # loads config
    config = load_config(args.config)

    # call sub command function
    # -> function is set by subparser.set_defaults(func=...)
    args.func(args)
