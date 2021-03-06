#!/usr/bin/python3
"""
main script for converting trac to github
"""

import os
import sys
import time
import yaml
import requests
import argparse
import logging
import re
import random

import wiki
import trac as tracapi

from github.MainClass import Github
from github import GithubException
import git

# logging.basicConfig(level=logging.WARN)
_log_root = logging.getLogger()
_log_format = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')

# setting up different log outputs (file and stdout)
_log_file_handler = logging.FileHandler('migrate.log')
_log_file_handler.setFormatter(_log_format)
_log_root.addHandler(_log_file_handler)

_log_stream_handler = logging.StreamHandler(sys.stdout)
_log_stream_handler.setFormatter(_log_format)
_log_root.addHandler(_log_stream_handler)

# get the logger for this application
log = logging.getLogger('TracMigrator')
log.setLevel(logging.INFO)


# regex to analyse GitHub repo ids (e.g. FreakyBytes/TracMigrator, or just TracMigrator)
_re_github_repo_name = re.compile(r'^(?:(?P<namespace>[\w\d\-_]+)/)?(?P<repo>[\w\d\-_]+)$', re.IGNORECASE | re.UNICODE)

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
            'client_id': None,
            'client_secret': None,
            'wiki_branch': 'gh-pages',
            'abuse_wait': 300,
            'default_namespace': None
        },
        'trac': {
            'base_url': None,
            'timeout': 15,
            'user': None,
            'password': None,
            'inter_trac_prefix': 'http://example.org/{trac_id}/wiki/',
            'keep_wiki_files': False,
            'wiki_filter_pages': ['CamelCase', 'InterMapTxt', 'InterTrac', 'InterWiki', 'PageTemplates', 'RecentChanges', 'SandBox', 'TitleIndex',
                'TracAccessibility', 'TracAdmin', 'TracBackup', 'TracBatchModify', 'TracBrowser', 'TracCgi', 'TracChangeset', 'TracEnvironment', 'TracFastCgi',
                'TracFineGrainedPermissions', 'TracGuide', 'TracImport', 'TracIni', 'TracInstall', 'TracInterfaceCustomization', 'TracLinks', 'TracLogging',
                'TracModPython', 'TracModWSGI', 'TracNavigation', 'TracNotification', 'TracPermissions', 'TracPlugins', 'TracQuery', 'TracReports',
                'TracRepositoryAdmin', 'TracRevisionLog', 'TracRoadmap', 'TracRss', 'TracSearch', 'TracStandalone', 'TracSupport', 'TracSyntaxColoring',
                'TracTicketsCustomFields', 'TracTickets', 'TracTimeline', 'TracUnicode', 'TracUpgrade', 'TracWiki', 'TracWorkflow', 'WikiDeletePage',
                'WikiFormatting', 'WikiHtml', 'WikiMacros', 'WikiNewPage', 'WikiPageNames', 'WikiProcessors', 'WikiRestructuredText', 'WikiRestructuredTextLinks'],
            'wiki_start_page': 'WikiStart',
        },
        'environments': [],
    }

    try:
        with open(path, 'r') as fs:
            loaded_config = yaml.safe_load(fs)

        config['trac'].update(loaded_config.get('trac', {}))
        config['github'].update(loaded_config.get('github', {}))
        if 'environments' in loaded_config and isinstance(loaded_config['environments'], (list, tuple)):
            config['environments'] = loaded_config['environments']
    except:
        log.exception('Failed loading config {path}. Using default values'.format(path=path))

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


def migrate_project(args, env, github=None, create_repo=False):

    # open local git repo
    if not env['git_repository']:
        # does not have a local git repo configured
        # throw an error
        log.error("Trac Env '{trac_id}' does not have a local git repo configured. Skipping".format(trac_id=env['trac_id']))
        return
    else:
        # load local git repo
        log.debug("Try to open local git repository at: {local_repo}".format(local_repo=env['git_repository']))
        local_repo = git.Repo(env['git_repository'])
        log.info("Opened local git repo {local_repo} for trac env {trac_id}".format(local_repo=local_repo.working_dir, trac_id=env['trac_id']))

    # init github connection, if required
    if github:
        repo_path = parse_repo_name(env['github_project'] or env['trac_id'], config['github']['default_namespace'])
        repo_name = '/'.join(filter(None, repo_path))
        #import pdb; pdb.set_trace()
        try:
            log.info("Try to find GitHub repo {repo_name}".format(repo_name=repo_name))
            github_repo = github.get_repo(repo_name)
            # try accessing the name, since the object is lazy loaded
            # if the repos does not exist yet, it will throw an exception
            github_repo.name
            log.info("Found GitHub repo {repo_name}".format(repo_name=github_repo.full_name))
        except:
            if create_repo is True:
                log.warn("Could not get GitHub Repo {repo_name} for Trac Env {trac_id}. Attempting to create it...".format(repo_name=repo_name, trac_id=env['trac_id']))
                if repo_path[0] and repo_path[0] != github.get_user().login:
                    # repo has an org path
                    github_org = github.get_organization(repo_path[0])
                    github_repo = github_org.create_repo(repo_path[1], has_issues=True, has_wiki=False, auto_init=False)
                else:
                    # create repo under current user
                    github_repo = github.get_user().create_repo(repo_path[1], has_issues=True, has_wiki=False, auto_init=False)
                log.info("Created GitHub Repo {repo_name}".format(repo_name=github_repo.full_name))
            else:
                log.error("Could not get GitHub Repo {repo_name} for Trac Env {trac_id}".format(repo_name=repo_name, trac_id=env['trac_id']))
                return
    else:
        github_repo = None

    # init Trac api object
    trac = tracapi.Trac(config['trac']['base_url'], env['trac_id'], user=config['trac']['user'], password=config['trac']['password'], timeout=config['trac']['timeout'])

    # start the fun :)
    try:
        converter = migrate_wiki(env, trac, local_repo, github_repo, disabled=True if args.no_wiki else False)
        if not args.no_tickets:
            migrate_tickets(env, trac, local_repo, github_repo, converter,
                    force=True if args.force_tickets is True else False,
                    continue_mode=True if args.continue_tickets is True else False)

        # push the git repo
        if not args.no_push:
            migrate_git_repo(env, trac, local_repo, github_repo)
    except KeyboardInterrupt:
        # migration was aborted by user
        log.warn("Execution was interrupted by user")
        return
    except BaseException:
        log.exception("Error while migrating Trac Env {trac_id}".format(trac_id=env['trac_id']))


def migrate_tickets(env, trac, local_repo, github_repo, converter, continue_mode=False, force=False):

    if not github_repo:
        log.warn("Skipping ticket migration, due to dry-run flag")
        return

    # ensure GitHub issues are enabled
    if not github_repo.has_issues:
        # name is required by GitHub Api
        github_repo.edit(name=github_repo.name, has_issues=True)

    # check if tickets already exist at GitHub (if first is empty to be precise, because the raw pagination api does not support len() )
    if len(github_repo.get_issues().get_page(0)) > 0 and force is False and continue_mode is False:
        # we cannot assure consistent ticket numbers, when already issues exist
        log.warn("GitHub project for Trac Env '{trac_id}' already contains issues. Skip ticket migration".format(trac_id=env['trac_id']))
        return

    migration_label = _get_or_create_label(github_repo, 'migrated', '662200')  # brown
    ticket_count = 1
    for ticket_number in trac.listTickets():

        # for continue mode, check if ticket already exists in GitHub
        if continue_mode is True:
            try:
                # try to get the ticket, if this succeeds skip this ticket
                github_repo.get_issue(ticket_number)
                log.info("Found issue #{ticket_number}, skip migration for this".format(ticket_number=ticket_number))
                continue
            except KeyboardInterrupt:
                # user abort -> propagate upwards
                raise KeyboardInterrupt
            except:
                # cannot get ticket/issue, so it might not exist
                pass

        ticket = trac.getTicket(ticket_number)
        log.info("Migrate ticket #{ticket_number}".format(ticket_number=ticket_number))

        if ticket['ticket_id'] > ticket_number:
            # create some dummy issues to cover deleted trac tickets
            _create_fake_tickets(github_repo, ticket_count, ticket['ticket_id'])

        # prepare the labels
        label_names = [ticket['attributes']['component'], ticket['attributes']['milestone'], ticket['attributes']['type'], ticket['attributes']['version'], ticket['attributes']['priority'], ticket['attributes']['resolution']] + ticket['attributes']['keywords'].split(',')
        log.debug("Raw label names: {labels}".format(labels=', '.join(label_names)))
        issue_labels = [_get_or_create_label(github_repo, name) for name in label_names] + [migration_label]
        issue_labels = list(filter(None, issue_labels))  # filter away all Nones
        log.debug("Used labels: {labels}".format(labels=', '.join([l.name for l in issue_labels])))

        #import pdb; pdb.set_trace()

        issue_text = []
        issue_text.append("""## Trac Ticket #{ticket_number}
**component:** {component}
**owner:** {owner}
**reporter:** {reporter}
**created:** {time_created}
**milestone:** {milestone}
**type:** {type}
**version:** {version}
**keywords:** {keywords}

{description}""".format(ticket_number=ticket_number, time_created=ticket['time_created'], time_changed=ticket['time_changed'], **ticket['attributes']))

        # apply change log as comments/edits
        change_count = 1
        issue_state = None
        for log_entry in sorted(trac.getTicketChangeLog(ticket_number), key=lambda log: log['time']):
            comment_text = """## comment {no}
**time:** {time}
**author:** {author}
""".format(no=change_count, **log_entry)

            if log_entry['field'] == 'comment':
                comment_text = comment_text + "\n\n" + converter.convert(log_entry['new_value'] + "\n")
            else:
                comment_text = comment_text + "\nUpdated **{field}** to **{new_value}**\n".format(**log_entry)

            if log_entry['field'] == 'status':
                issue_state = _ticket_state[log_entry['new_value']]

            issue_text.append(comment_text)
            change_count += 1

        while True:
            try:
                # finally migrate the ticket
                issue = github_repo.create_issue(
                    title=ticket['attributes']['summary'],
                    labels=issue_labels,
                    body='\n\n'.join(issue_text),
                )
                break  # if everything went well, just break free
            except GithubException as e:
                if e.data.get('documentation_url', True) in ('https://developer.github.com/v3#abuse-rate-limits', True):
                    log.warn('triggered abuse rate limit. Wait {min.1f} minutes'.format(min=config['github'].get('abuse_wait', 300)/60))
                    time.sleep(float(config['github'].get('abuse_wait', 300)))
                else:
                    raise e

        if issue_state:
            issue.edit(state=issue_state)

        log.info("Migrated ticket #{ticket_number} with {change_count} log entries: {title}".format(ticket_number=ticket_number, change_count=change_count-1, title=issue.title))


# gh full_name -> label name -> label obj
_label_cache = {}
def _get_or_create_label(github, label_name, color=None):

    if not label_name:
        return None

    # check, if we got the label already cached
    label = None
    if github.full_name in _label_cache and _label_cache[github.full_name]:
        if label_name in _label_cache[github.full_name] and _label_cache[github.full_name][label_name]:
            return _label_cache[github.full_name][label_name]

    if not label:
        # not in cache, try to get it or create it
        try:
            label = github.get_label(label_name)
        except:
            if not color:
                color = ''.join([random.choice('0123456789ABCDEF') for x in range(6)])

            log.info("Create label '{label}' with color #{color} for {repo_name}".format(label=label_name, color=color, repo_name=github.full_name))
            label = github.create_label(label_name, color)

        if github.full_name not in _label_cache:
            _label_cache[github.full_name] = {label_name: label}
        else:
            _label_cache[github.full_name][label_name] = label

        return label


def _create_fake_tickets(github, start=0, end=0):

    log.info("Create {num} fake issues".format(num=end-start))
    for idx in range(start, end):
        issue = github.create_issue("Deleted Trac Ticket #{no}".format(no=idx))
        issue.edit(state='closed')


def migrate_wiki(env, trac, local_repo, github_repo, disabled=False):
    log.info("Start wiki conversion for Trac Env {trac_id}".format(trac_id=env['trac_id']))

    # list all wiki pages in the trac env
    wiki_pages = trac.listWikiPages()
    log.debug("Found {num} wiki pages".format(num=len(wiki_pages)))

    # init wiki->MarkDown converter
    converter = wiki.WikiConverter(
            pages={page: None for page in wiki_pages},  # currently not used
            prefixes={trac_env['trac_id']: config['trac']['inter_trac_prefix'].format(**trac_env) for trac_env in config['environments']}  # generate prefix map, so inter_wiki links get properly redirected
        )

    if disabled:
        # stop here, so only the converter gets initialized
        return converter

    # step 0: check if wiki branch already exists
    for branch in local_repo.branches:
        if branch.name == config['github'].get('wiki_branch', 'gh-pages'):
            log.info("wiki branch already exists for this repo. Skip wiki migration")
            # just make sure, the converter is returned
            return converter

    # step 1: cut a hole in the box / or create an orphan git branch ;)
    log.debug("Creating orphaned branch for wiki pages")
    wiki_head = git.Head(local_repo, 'refs/heads/{branch}'.format(branch=config['github'].get('wiki_branch', 'gh-pages') or 'gh-pages'))
    wiki_head.checkout(force=True, orphan=True)

    # remove everything from the index and then from the repo
    # (it remains existing in the other branches)
    log.debug("Remove remaining files in working dir")
    repo_path = os.path.normpath(os.path.expanduser(env['git_repository']))
    for obj in local_repo.index.remove('.', r=True):
        log.debug("remove file {f}".format(f=obj))
        file_path = os.path.join(repo_path, obj)
        try:
            os.remove(file_path)
        except BaseException as e:
            log.warn("error while attempting to remove {f}".format(f=file_path))

    # iterate over all wiki pages
    for page in wiki_pages:
        # skip default trac wiki pages. They cause problems and are not
        # necessary anymore...
        if page in config['trac']['wiki_filter_pages']:
            continue

        log.info("Convert wiki page {page} for Trac Env {trac_id}".format(page=page, trac_id=env['trac_id']))
        content = trac.getWikiPageText(page)

        #import pdb; pdb.set_trace()
        if config['trac']['keep_wiki_files'] is True:
            # save wiki text as .wiki file
            fs_name = os.path.join(repo_path, "{page}.wiki".format(page=page))
            os.makedirs(os.path.dirname(fs_name), exist_ok=True)
            with open(fs_name, 'w') as fs:
                fs.write(content)
                fs.flush()
            local_repo.index.add([fs_name, ])

        # convert it
        md = converter.convert(content)
        fs_name = os.path.join(repo_path, "{page}.md".format(page=page))
        os.makedirs(os.path.dirname(fs_name), exist_ok=True)
        with open(fs_name, 'w') as fs:
            fs.write(md)
            fs.flush()
        local_repo.index.add([fs_name, ])

        # link start page to index.md
        if page == config['trac']['wiki_start_page']:
            # is WikiStart -> create symlink to index.md
            log.info("Link {page} to index.md, to serve as start page".format(page=page))
            repo_dir_fd = os.open(repo_path, os.O_RDONLY)
            os.symlink("{page}.md".format(page=page), "index.md", dir_fd=repo_dir_fd)
            os.close(repo_dir_fd)
            local_repo.index.add(["index.md", ])

        # fetch wiki attachements
        for attachement in trac.listWikiAttachements(page):
            fs_name = os.path.join(repo_path, attachement)
            os.makedirs(os.path.dirname(fs_name), exist_ok=True)
            with open(fs_name, 'wb') as fs:
                log.debug("Store Wiki Attachement {att} for page {page}".format(att=attachement, page=page))
                fs.write(trac.getWikiAttachement(attachement))
                fs.flush()
            local_repo.index.add([fs_name, ])

    # commit all converted (and non-converted) files
    local_repo.index.commit('converted wiki pages')

    return converter


def migrate_git_repo(env, trac, local_repo, github_repo):

    if not github_repo:
        log.warn("Skip git migration, due to dry-run flag")
        return

    # create a new remote, and if exists, checks the url
    log.info("Update git remote configuration for {local_repo}".format(local_repo=local_repo.working_dir))
    try:
        remote = local_repo.create_remote('github', github_repo.ssh_url)
    except:
        remote = local_repo.remotes['github']
        if github_repo.ssh_url not in remote.urls:
            remote.set_url(github_repo.ssh_url)

    # TODO add proper refspecs
    log.info("Push {local_repo} to {github_repo} for Trac Env {trac_id}".format(local_repo=local_repo.working_dir, github_repo=github_repo.full_name, trac_id=env['trac_id']))
    refspec = ''
    #remote.pull(refspec=refspec)
    remote.push(refspec=refspec)
    log.info("Done pushing")


def do_save_config(args):
    """
    Just takes the loaded config and saves it again.
    Good for generating a empty config template
    """
    save_config(args.config, config)


def do_get_envs(args):
    # get available envs and store them in the config

    env_map = {}
    if args.override is True or 'environments' not in config or not config['environments']:
        # remove old environments from config
        config['environments'] = []
    else:
        # create mapping from env trac_ids to list indexies
        for index, env in enumerate(config['environments']):
            if env['trac_id']:
                env_map[env['trac_id']] = index

    count = 0
    for env in tracapi.listTracEnvironments(config['trac']['base_url'], timeout=config['trac']['timeout']):
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
        github = _login_github(config['github'])
    else:
        github = None

    count = 0
    for env in config['environments']:
        if env['enabled'] is False:
            continue

        # do the work
        log.info('Start migrating project {}'.format(env['trac_id']))
        migrate_project(args, env, github=github, create_repo=args.create)
        count += 1

    log.info('Migrated {} projects'.format(count))


def _login_github(github_config):

    github = Github(github_config['token'], client_id=github_config.get('client_id', None), client_secret=github_config.get('client_secret', None))

    if not github.get_user():
        log.error('Error accessing GitHub')
        raise RuntimeError('Could not login to Github')

    return github


if __name__ == '__main__':
    # main argument parser
    parser = argparse.ArgumentParser(conflict_handler='resolve')
    parser.add_argument('-c', '--config', help='path to the config file', default='config.yml')
    parser.add_argument('-v', '--verbose', help='increase log level to TRACE', default=False, action='store_true')
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
    migrate_parser.add_argument('--no-wiki', help='disables the wiki migration', default=False, action='store_true')
    migrate_parser.add_argument('--force-tickets', help='forces the migration of tickets, even when the GitHub project already contains issues', default=False, action='store_true')
    migrate_parser.add_argument('--continue-tickets', help='Checks if a ticket/issue number already exists, before migration it. DOES NOT check/alter the content of existing issues', default=False, action='store_true')
    migrate_parser.add_argument('--no-tickets', help='disables the ticket migration', default=False, action='store_true')
    migrate_parser.add_argument('--no-push', help='does not push the repository to github', default=False, action='store_true')
    migrate_parser.set_defaults(func=do_migrate)

    # parse it...
    args = parser.parse_args()

    # increase log level, if verbose flag is set
    if args.verbose:
        log.setLevel(logging.DEBUG)

    # loads config
    config = load_config(args.config)

    # call sub command function
    # -> function is set by subparser.set_defaults(func=...)
    if hasattr(args, 'func') and args.func:
        args.func(args)
    else:
        parser.print_help()
