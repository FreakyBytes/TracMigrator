#!/usr/bin/python3
"""
main script for converting trac to github
"""

import yaml
import requests
import argparse
import logging
import re

import wiki
import trac

from github.MainClass import Github

logging.basicConfig(level=logging.WARN, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
log = logging.getLogger('TracMigrator')
log.setLevel(logging.INFO)

# regex to analyse GitHub repo ids (e.g. FreakyBytes/TracMigrator, or just TracMigrator)
_re_github_repo_name = re.compile(r'^(?:(?P<namespace>[\w\d]+)/)?(?P<repo>[\w\d]+)$', re.IGNORECASE | re.UNICODE)

def load_config(path):
    config = {
        'github': {
            'token': None,
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


def parse_repo_name(name, default_namespace=None):
    """
    takes in strings like 'FreakyBytes/TracMigrator' and 'TracMigrator' and
    return (namespace, repo_name)
    """
    if not name:
        return (None, None)

    match = _re_github_repo_name.match(name)
    if not match:
        return (None, None)
    
    groups = match.groupdict()
    return (groups.get('namespace', default_namespace) or default_namespace, groups.get('repo', None))


def migrate_project(env, github=None, create_repo=False):

    if github:
        repo_name = '/'.join(filter(None, parse_repo_name(env['github_project'] or env['trac_id'], config['github']['default_namespace'])))
        try:
            log.info("Try to find GitHub repo '{repo_name}'".format(repo_name=repo_name))
            github_repo = github.get_repo(repo_name)
            # try accessing the name, since the object is lazy loaded
            # if the repos does not exist yet, it will throw an exception
            github_repo.name
        except:
            if create_repo is True:
                log.warn("Could not get GitHub Repo '{repo_name}' for Trac Env '{trac_id}'. Attempting to create it...".format(repo_name=repo_name, trac_id=env['trac_id']))
                github_repo = github.get_user().create_repo(repo_name)
            else: 
                log.error("Could not get GitHub Repo '{repo_name}' for Trac Env '{trac_id}'".format(repo_name=repo_name, trac_id=env['trac_id']))
                return
    #import pdb; pdb.set_trace()
    return


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
        
    count = 0
    for env in  trac.listTracEnvironments(config['trac']['base_url'], timeout=config['trac']['timeout']):
        log.info('Found Trac environment {id}'.format(id=env['trac_id']))
        if env['trac_id'] in env_map:
            continue

        config['environments'].append(env)
        count += 1
    
    log.info('Found {} new Trac environments'.format(count))
    save_config(args.config, config)


def do_migrate(args):
    pass

    if args.dry_run is False:
        # results are supposed to be pushed to github (default)
        # better check if github is reachable
        github = Github(config['github']['token'])
        if not github.get_user():
            log.error('Error accessing GitHub')
            return
    else:
        github = None

    count = 0
    for env in config['environments']:
        if env['enabled'] is False:
            continue

        # do the work
        log.info('Start migrating project {}'.format(env['trac_id']))
        migrate_project(env, github=github, create_repo=args.create)
        count += 1

    log.info('Migrated {} projects'.format(count))


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
    migrate_parser.add_argument('--create', help='creates all non-existing repositories on GitHub - this can get messy', default=False, action='store_true')
    migrate_parser.set_defaults(func=do_migrate)

    # parse it...
    args = parser.parse_args()
    # loads config
    config = load_config(args.config)

    # call sub command function
    # -> function is set by subparser.set_defaults(func=...)
    args.func(args)
