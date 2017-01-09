#!/usr/bin/python3
"""
main script for converting trac to github
"""

import os
import yaml
import requests
import argparse
import logging
import re

import wiki
import trac as tracapi

from github.MainClass import Github
import git

logging.basicConfig(level=logging.WARN, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
log = logging.getLogger('TracMigrator')
log.setLevel(logging.INFO)

# regex to analyse GitHub repo ids (e.g. FreakyBytes/TracMigrator, or just TracMigrator)
_re_github_repo_name = re.compile(r'^(?:(?P<namespace>[\w\d]+)/)?(?P<repo>[\w\d]+)$', re.IGNORECASE | re.UNICODE)

# dict to translate Trac ticket status in GitHub issue state (open/close)
_ticket_state = {
    'new': 'open',
    'reopened': 'open',
    'assigned': 'open',
    'accepted': 'open',
    'closed': 'closed',
}

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
            'inter_trac_prefix': 'http://example.org/{trac_id}/wiki/',
            'keep_wiki_files': False,
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

    # open local git repo
    if not env['git_repository']:
        # does not have a local git repo configured
        # throw an error
        log.error("Trac Env '{trac_id}' does not have a local git repo configured. Skipping".format(trac_id=env['trac_id']))
        return
    else:
        # load local git repo
        local_repo = git.Repo(env['git_repository'])

    # init github connection, if required
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
    
    # init Trac api object
    trac = tracapi.Trac(config['trac']['base_url'], env['trac_id'], user=config['trac']['user'], password=config['trac']['password'], timeout=config['trac']['timeout'])

    # start the fun :)
    try:
        converter = migrate_wiki(env, trac, local_repo, github_repo)
        migrate_tickets(env, trac, local_repo, github_repo, converter)
    except BaseException as e:
        log.error("Error while migrating Trac Env '{trac_id}'".format(trac_id=env['track_id'], e)


def migrate_tickets(env, trac, local_repo, github_repo, converter):
    
    # check if tickets already exist at GitHub
    if len(github_repo.get_issues()) > 0:
        # we cannot assure consistent ticket numbers, when already issues exist
        log.warn("GitHub project for Trac Env '{trac_id}' already contains issues. Skip ticket migration".format(trac_id=env['trac_id']))
        return

    migration_label = self._get_or_create_label(github_repo, 'migrated', 'brown')
    ticket_count = 1
    for ticket_number in trac.listTickets():
        ticket = trac.getTicket(ticket_number)
        log.info("Migrate ticket #{ticket_number}".format(ticket_number=ticket_number))

        if ticket['ticket_id'] > ticket_number:
            # create some dummy issues to cover deleted trac tickets
            self._create_fake_tickets(github_repo, ticket_count, ticket['ticket_id'])

        # the Ticket itself
        labels = [self._get_or_create_label(github_repo, name) for name in [ticket['attributes']['component'], ticket['attributes']['milestone'], ticket['attributes']['type'], ticket['attributes'['version'], ticket['attributes']['priority'], ticket['attributes']['resolution']] + ticket['attributes']['keywords'].split(',')
        labels += [migration_label]
        labels = filter(None, labels)  # filter away all None's
        issue = github_repo.create_issue(
                title=ticket['attributes']['summary'],
                body="""**component:** {component}
**owner:** {owner}
**reporter:** {reporter}
**created:** {time_created}
**milestone:** {milestone}
**type:** {type}
**version:** {version}
**keywords:** {keywords}

{description}""".format(time_create=ticket['time_create'], time_changed=ticket['time_changed'], **ticket['attributes']),
                labels=labels
            )

        # apply change log as comments/edits
        for log_entry in sorted(trac.getTicketChangeLog(ticket_number), key='time'):
            comment_text = """
**time:** {time}
**author:** {author}
""".format(**log_entry)
            if log_entry['field'] == 'comment':
                comment_text = comment_text + "\n\n" + converter.convert(log_entry['new_value'])
            else:
                comment_text = comment_text + "\nUpdated **{field}** to **{new_value}**".format(**log_entry)

            issue.create_comment(comment_text)
            if log_entry['field'] == 'status':
                issue.edit(state=_ticket_state[log_entry['new_value'])


def _get_or_create_label(github, label_name, color='pink'):
    
    if not label_name:
        return None

    try:
        return github.get_label(label_name)
    except:
        return github.create_label(label_name, color)


def _create_fake_tickets(github, start=0, end=0):
    
    log.info("Create {num} fake issues".format(num=end-start))
    for idx in range(start, end):
        issue = github.create_issue("Deleted Trac Ticket #{no}".format(no=idx)
        issue.edit(state='closed')


def migrate_wiki(env, trac, local_repo, github_repo):
    
    # step 1: cut a hole in the box / or create an orphan git branch ;)
    wiki_head = git.Head(local_repo, 'refs/heads/{branch}'.format(branch=config['github'].get('wiki_branch', 'gh-pages') or 'gh-pages'))
    wiki_head.checkout(force=True, orphan=True)
    # remove everything from the index and then from the repo
    # (it remains existing in the other branches)
    for obj in local_repo.index.remove('*'):
        os.remove(os.path.join(env['git_repository'], obj))

    # list all wiki pages in the trac env
    wiki_pages = trac.listWikiPages()
    # init wiki->MarkDown converter
    converter = wiki.WikiConverter(
            pages={page: None for page in wiki_pages},  # currently not used
            prefixes={trac_env['trac_id']: config['trac']['inter_trac_prefix'].format(**trac_env) for trac_env in config['environments']}  # generate prefix map, so inter_wiki links get properly redirected
        )

    # iterate over all wiki pages
    for page in wiki_pages:
        content = trac.getWikiPageText(page)

        if config['trac']['keep_wiki_files'] is True:
            # save wiki text as .wiki file
            fs_name = os.path.join(env['git_repository'], "{page}.wiki".format(page=page)
            with open(fs_name, 'w') as fs:
                fs.write(content)
            local_repo.index.add(fs_name)

        # convert it
        md = converter.convert(content)
        fs_name = os.path.join(env['git_repository'], "{page}.md".format(page=page)
        with open(fs_name, 'w') as fs:
            fs.write(md)
        local_repo.index.add(fs_name)

        # TODO fetch wiki attachements!

    # commit all converted (and non-converted) files
    local_repo.index.commit('converted wiki pages')

    return converter


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
