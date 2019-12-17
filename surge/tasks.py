import re

from fabric import task
from invoke import Collection
from invoke.exceptions import AuthFailure, Exit
from fabulous.color import green, red, blue, cyan, yellow, magenta
from patchwork.files import exists

from surge.decorators import skip_if_not, needs_django, mtask


DEFAULT_SETTINGS = {
    'deploy': {
        'require_clean': True,
        'branch_name': 'master',
        'django_project': True,
        'skip_syncdb': False,
        'skip_migrate': False,
        'restart_nginx': False,
        'bounce_services_only_if_running': False,
        'os_service_manager': 'upstart',
        'require_remote_clean': True,
    }
}


@mtask(default=True)
def dummy(c, require_clean=None):
    '''
    I am a docstring.
    '''
    
    print(require_clean)

@task
def sudo_check(c):
    print(cyan("Validating sudo."))
    
    try:
        c.sudo('echo')
    except AuthFailure:
        print(red("Could not obtain sudo!"))
        return False
    else:
        return True

@task
def show_settings(c):
    unpassed = cyan
    default = green
    overriden = magenta
    
    print('{} {} {}'.format(unpassed('Configured'), default('Default'), overriden('Overridden')))
    
    ###TODO: needs refactor to handle hierarchical settings
    for k,v in sorted(c.config.items(), key=lambda x: x[0]):
        default_value = DEFAULT_SETTINGS.get(k)
        
        if default_value:
            if default_value == v:
                outcolor = default
            else:
                outcolor = overriden
        else:
            outcolor = unpassed

        print(outcolor(f"{k} = {v}"))

@task
@skip_if_not('require_clean')
def is_local_clean(c, require_clean=None):
    """
    Checks that the local git work area is clean or not

    runs:
    git status --porcelain
    """

    print(cyan("Ensuring local working area is clean..."))
    has_changes = c.local("git status --porcelain")
    
    if has_changes:
        raise Exit(red("Your working directory is not clean."))
    else:
        return True

@task
@skip_if_not('require_remote_clean')
def is_remote_clean(c, deploy_path=None):
    """
    Checks that the remote git work area is clean or not

    runs:
    git --work-tree=deploy_path --git-dir=deploy_path/.git status --porcelain
    """
    
    ###FIXME: should already be merged
    deploy_path = deploy_path or c.deploy.deploy_path

    print(cyan("Ensuring remote working area is clean..."))
    git_cmd = f"git --work-tree={deploy_path} --git-dir={deploy_path}/.git"
    has_changes = c.run(f'{git_cmd} status --porcelain')
    
    if has_changes:
        raise Exit(red("Remote working directory is not clean."))
    else:
        return True

@task
def fix_ownerships(c, deploy_path=None, chown_target=None, user=None, group=None):
    """
    Ensure the project files have the USER:GROUP ownership

    runs:
    chown USER:GROUP --recursive *
    chown USER:GROUP --recursive .git*
    chown USER:GROUP --recursive .env|env (if these exist)
    """
    
    ###FIXME: should already be merged
    deploy_path = deploy_path or c.deploy.deploy_path
    user = user or c.deploy.user
    group = group or c.deploy.group
    chown_target = chown_target or c.deploy.chown_target or f'{user}:{group}'

    with c.cd(deploy_path):
        print(cyan('Fixing project ownerships'))
        c.sudo(f'chown {chown_target} --recursive .')
        print()

@task
def pull(c, deploy_path=None, branch_name=None):
    """
    git fetch; git checkout; git pull

    runs:
    git fetch
    git checkout {branch from settings or supplied}
    git pull

    :branch= sets the desired branch
    """
    
    deploy_path = deploy_path or c.deploy.deploy_path ###FIXME: should already be merged
    branch = branch_name or c.deploy.BRANCH_NAME ###FIXME: should already be merged

    print(cyan(f"Pulling from {branch}"))
    
    with c.cd(deploy_path):
        c.run('git checkout {branch}')
        c.run('git pull')

@task
def full_pull(c):
    """
    fix_ownerships, pull, update_submodules, fix_ownerships

    runs:
    fix_ownerships
    pull
    update_submodules
    fix_ownerships

    :branch= sets the desired branch
    """
    
    fix_ownerships(c)
    pull(c)
    update_submodules(c)
    fix_ownerships(c)

@task(aliases=['sup'])
def update_submodules(c, deploy_path=None):
    """
    Init and update the git submodules for the project

    runs:
    git submodule init
    git submodule update
    """
    
    deploy_path = deploy_path or c.deploy.deploy_path ###FIXME: should already be merged
    
    with cd(deploy_path):
        print(cyan('Initializing and updating submodules recursively'))
        c.run('git submodule update --init --recursive')
        print("")

@task
def fix_logfile_permissions(c, deploy_path=None, log_path=None):
    """
    Sets the correct file permissions on the files in the log_path

    runs:
    chmod --preserve-root --changes a+r,ug+w --recursive logs_path
    """
    
    ###FIXME: should already be merged
    deploy_path = deploy_path or c.deploy.deploy_path
    log_path = log_path or c.deploy.log_path or c.deploy.logs_path

    if log_path:
        with c.cd(deploy_path):
            print(cyan("Ensuring proper permissions on log files (0664)"))
            c.sudo(f"chmod --preserve-root --changes --recursive a=rX,ug+w {log_path}")
            print("")

@task
def install_requirements(c, deploy_path=None):
    """
    Installs the project's requirements from the project's requirements.txt file
    into the project's activated virtual environment.

    runs:
    pip install -r requirements.txt
    """
    
    ###FIXME: should already be merged
    deploy_path = deploy_path or c.deploy.deploy_path
    
    with cd(deploy_path):
        print(cyan("Installing pinned dependencies from Pipfile.lock"))
        run("pipenv sync")

@task
@needs_django
def collectstatic(c, deploy_path=None, user=None, group=None):
    """
    Collect static assets for a Django project

    runs:
    manage.py collectstatic -v0 --noinput
    """
    
    ###FIXME: should already be merged
    deploy_path = deploy_path or c.deploy.deploy_path
    user = user or c.deploy.user
    group = group or c.deploy.group
    chown_target = chown_target or c.deploy.chown_target or f'{user}:{group}'

    print(cyan("Collecting static resources"))
    
    with c.cd(deploy_path):
        # Setting verbose to minimal outupt
        # We aren't going to prompt if we really want to collectstatic
        c.run("./manage.py collectstatic -v0 --noinput")

        # Get the settings module
        out = c.run("./manage.py diffsettings --all | grep SETTINGS_MODULE")
        split_sm = out.split("=")
        sm = None
        
        if len(split_sm) > 1:
            # Sometimes ./manage.py throws errors that end up in this output
            re_split_sm = re.split(r'(\r\n|\n|\r)', split_sm[1])[0]
            
            # Get the settings module
            m = re.search(r'[\'|\"].*?[\'|\"]', re_split_sm)
            sm = m and m.group().strip()

        # Get the STATIC_ROOT path
        static_root_path = c.run(f"pipenv run python -c 'from {sm} import STATIC_ROOT; print(STATIC_ROOT)'") or 'collected-assets'

        # Touch the .less/.js files in STATIC_ROOT
        if exists(c, static_root_path):
            print(cyan(f'Touching *.less and *.js in {static_root_path}'))
            
            # Exclude the _cache directory used by Compress
            c.run(f'find {static_root_path} \( -name "*.less" -or -name "*.js" \) -not -path "*/_cache*/*" -exec touch {{}} +')
            
            # Only fix the ownerships if collectstatic is called from the command line
            ###FIXME: need to implement called_task
            if c.called_task == 'collectstatic':
                c.sudo(f'chown {chown_target} --recursive {static_root_path}')
            
            print("")
        else:
            print(red('Could not locate the STATIC_ROOT path for this project, skipping touches.\n'))



@task
@needs_django
@skip_if_not('skip_migrate', False)
def run_migrations(c, extra_migrations=None):
    """
    Runs the Django manaagement command migrate for django_project=True

    runs:
    manage.py migrate
    """
    
    ###FIXME: should already be merged
    extra_migrations = extra_migrations or c.deploy.extra_migrate_for_databases

    print(cyan("Running migrations"))
    with c.cd(deploy_path):
        c.run("./manage.py migrate")

        if extra_migrations:
            print("")
            print(cyan("Running extra migrations"))
            
            for db in extra_migrations:
                c.run(f"./manage.py migrate --database {db}")


@task
def run_extras(c, extra_commands=[]):
    """
    Runs any extra commands on HOST in extra_commands list of the settings
    """
    
    ###FIXME: should already be merged
    extra_commands = extra_commands or c.deploy.extra_commands

    with c.cd(deploy_path):
        for cmd in extra_commands:
            print(cyan(f'Extra:  {cmd}'))
            c.run(cmd)

@task
def restart_nginx(c, os_service_manager=None):
    """
    Restart the nginx service on HOST

    runs:
    sudo service nginx restart
    """
    
    ###FIXME: should already be merged
    os_service_manager = os_service_manager or c.deploy.os_service_manager

    print(cyan("Restarting Nginx"))
    
    if os_service_manager == 'upstart':
        c.sudo('service nginx restart')
    elif os_service_manager == 'systemd':
        c.sudo('systemctl restart nginx')
    else:
        raise ValueError(f'invalid os_service_manager setting: {os_service_manager}')

@task
def bounce_services(c, bounce_services=[], bounce_services_only_if_running=None, os_service_manager=None):
    """
    Restarts the services on HOST from the bounce_services list of the settings.

    runs:
    sudo service X restart (where X is each member of the bounce_services list)

    :restart_nginx=True will also restart nginx
    """
    
    ###FIXME: should already be merged
    bounce_services = bounce_services or c.deploy.bounce_services
    bounce_services_only_if_running = bounce_services_only_if_running or c.deploy.bounce_services_only_if_running
    os_service_manager = os_service_manager or c.deploy.os_service_manager

    if not bounce_services:
        return None

    STATUS = {
        '+': 'Running',
        '-': 'Stopped/Waiting',
        '?': 'Unknown'
    }

    if bounce_services_only_if_running:
        print(cyan("Bouncing processes...(BOUNCING_SERVICES_ONLY_IF_RUNNING)"))
    else:
        print(cyan("Bouncing processes..."))
    
    print(cyan(bounce_services))
    
    there = []
    not_there = []
    for service in bounce_services:
        if os_service_manager == 'upstart':
            status = c.sudo(f'service {service} status', quiet=True)
            
            if re.search(r'unrecognized service', status):
                not_there.append(service)
                continue
            
            if re.search(f'{service} stop/waiting', status):
                sglyph = '-'
            elif re.search(f'{service} start/running', status):
                sglyph = '+'
            else:
                sglyph = '?'
        elif os_service_manager == 'systemd':
            status = c.sudo(f'systemctl status --full --no-pager {service}', quiet=True)
            
            if 'Loaded: not-found' in status:
                not_there.append(service)
            else:
                if 'Active: inactive' in status:
                    sglyph = '-'
                elif 'Active: active (running)' in status:
                    sglyph = '+'
                else:
                    sglyph = '?'
        else:
            raise ValueError(f'invalid os_service_manager setting: {os_service_manager}')
        
        there.append((sglyph, service))

    for status, service in there:
        print(green(f"{service}: {STATUS[status]}"))
        if status != '+' and bounce_services_only_if_running:
            print(red(f"{service} NOT bouncing"))
            continue
        
        if os_service_manager == 'upstart':
            c.sudo(f'service {service} restart')
        elif os_service_manager == 'systemd':
            c.sudo(f'systemctl restart {service}')
        else:
            pass ###intentional - already checked

    for s in not_there:
        print(magenta(f"{s} not found on {env.deploy_settings.HOST}"))

    if bool_opt('restart_nginx', kwargs, default=False): ###FIXME
        restart_nginx(c)


@task
def services_status(c, bounce_services=[]):
    """
    Returns a list of the current status of the services on HOST from the bounce_services list.

    runs:
    sudo service X status (where x is each member of the bounce_services list)
    """
    
    ###FIXME: should already be merged
    bounce_services = bounce_services or c.deploy.bounce_services
    os_service_manager = os_service_manager or c.deploy.os_service_manager

    for service in bounce_services:
        if os_service_manager == 'upstart':
            status = c.sudo(f'service {service} status', quiet=True)
            color = green
            
            if re.search(f'{service} stop/waiting', status):
                color = red
            
            print(color(status)) ###FIXME
        elif os_service_manager == 'systemd':
            status = c.sudo(f'systemctl status --full --no-pager {service}', quiet=True)
            color = green
            
            if 'Active: inactive' in status or 'Active: failed' in status:
                color = red
            
            print(color(status))
        else:
            raise ValueError(f'invalid os_service_manager setting: {os_service_manager}')

@task
def update_crontab(c, cron_file=None, crontab_owner=None):
    """
    Replaces the current crontab for crontab_owner on HOST with cron_file

    runs:
    sudo crontab -u crontab_owner cron_file
    """
    
    ###FIXME: should already be merged
    cron_file = cron_file or c.deploy.cron_file
    crontab_owner = crontab_owner or c.deploy.crontab_owner
    
    if cron_file and crontab_owner:
        print(green("Updating crontab..."))
        c.sudo(f'crontab -u {crontab_owner} {cron_file}')
        print("")

@task
@needs_django
@skip_if_not('skip_syncdb', False)
def sync_db(c, deploy_path=None):
    """
    Runs the Django management command syncdb for DJANGO_PROJECT=True

    runs:
    manage sync_db
    """
    
    ###FIXME: should already be merged
    deploy_path = deploy_path or c.deploy.deploy_path

    print(cyan("Sync DB"))
    with c.cd(deploy_path):
        c.run("./manage.py syncdb")

# @task(default=True)
@task
def full_deploy(c, skip_migrate=None):
    """:require_clean=False will deploy even if local repo is not clean

    Requirements:
        - Must have a clean working directory
        - Remote must have a clean working directory

    Steps:
        - Change to project directory
        - Activating environment
        - Install all requirements
        - Run git fetch to pull down all changes
        - Updating submodules
        - Changing owner:group to draftboard
        - Bounce the webserver

    runs:
    fix_ownerships
    pull
    update_submodules
    fix_logfile_permissions
    install_requirements
    collectstatic
    sync_db
    run_migrations
    run_extras
    fix_ownerships
    bounce_services
    update_crontab
    """
    
    ###FIXME: should already be merged
    skip_migrate = skip_migrate or c.deploy.skip_migrate


    print(green("Beginning deployment..."))
    print("")

    print(blue('Checking pre-requisites...'))

    is_local_clean(c)

    is_remote_clean(c)

    print("")
    print(green("Starting deployment..."))
    print("")

    print(green("Updating environment..."))

    fix_ownerships(c)
    pull(c)
    update_submodules(c)
    fix_logfile_permissions(c)
    install_requirements(c)
    collectstatic(c)
    sync_db(c)
    
    if not skip_migrate:
        run_migrations(c)
    
    run_extras(c)

    # post fix owners after checkout and other actions
    fix_ownerships(c)
    bounce_services(c)
    update_crontab(c)

    print(green("Done!"))


@task
def full_deploy_with_migrate(c):
    full_deploy(c, skip_migrate=False)


namespace = Collection(
    dummy,
    sudo_check,
    show_settings,
    is_local_clean,
    is_remote_clean,
    fix_ownerships,
    pull,
    full_pull,
    update_submodules,
    fix_logfile_permissions,
    install_requirements,
    collectstatic,
    run_migrations,
    run_extras,
    restart_nginx,
    bounce_services,
    services_status,
    update_crontab,
    sync_db,
    full_deploy,
    full_deploy_with_migrate,
)
namespace.configure(DEFAULT_SETTINGS)
