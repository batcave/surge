import re

from fabric.context_managers import prefix
from fabric.contrib.files import exists
from fabulous import green, red, blue, cyan, yellow, magenta


@task
def sudo_check(c):
    print(cyan("Validating sudo."))
    result = c.sudo('echo "Got it!"')
    if result:
        return True
    else:
        print(red("Could not obtain sudo!"))
        return False

@task
def show_settings():
    print("\n({0} {1} {2})\n".format(cyan('Configured'),
                                     green('Default'),
                                     magenta('Overridden Default')))
    for s in sorted(env.deploy_settings.settings.keys()):
        v = env.deploy_settings.settings[s]
        outcolor = cyan
        if s in DEFAULT_SETTINGS:
            outcolor = green if v == DEFAULT_SETTINGS[s] else magenta

        print(outcolor("{0} = {1}".format(s, v)))
        
@task
@skip_if_not('REQUIRE_CLEAN')
def is_local_clean(*args, **kwargs):
    """
    Checks that the local git work area is clean or not

    runs:
    git status --porcelain
    """

    print(cyan("Ensuring local working area is clean..."))
    has_changes = local("git status --porcelain", capture=True)
    if has_changes:
        abort(red("Your working directory is not clean."))

    return not has_changes

@task
@skip_if_not('REQUIRE_REMOTE_CLEAN')
def is_remote_clean(*args, **kwargs):
    """
    Checks that the remote git work area is clean or not

    runs:
    git --work-tree=DEPLOY_PATH --git-dir=DEPLOY_PATH/.git status --porcelain
    """

    print(cyan("Ensuring remote working area is clean..."))
    git_cmd = "git --work-tree={0} --git-dir={0}/.git".format(env.deploy_settings.DEPLOY_PATH)
    has_changes = run(git_cmd + " status --porcelain")
    if has_changes:
        abort(red("Remote working directory is not clean."))

    return not has_changes

@task
def fix_ownerships(*args, **kwargs):
    """
    Ensure the project files have the USER:GROUP ownership

    runs:
    chown USER:GROUP -R *
    chown USER:GROUP -R .git*
    chown USER:GROUP -R .env|env (if these exist)
    """

    with cd(env.deploy_settings.DEPLOY_PATH):
        print(cyan('Fixing project ownerships'))
        sudo(f'chown {env.deploy_settings.CHOWN_TARGET} -R *')
        sudo(f'chown {env.deploy_settings.CHOWN_TARGET} -R .git*')
        sudo(f'chown {env.deploy_settings.CHOWN_TARGET} -R .venv*')
        sudo(f'if [ -e .env ]; then chown {env.deploy_settings.CHOWN_TARGET} -R .env; fi')
        sudo(f'if [ -e env ]; then chown {env.deploy_settings.CHOWN_TARGET} -R env; fi')
        print("")

@task
@can_override_settings
def pull(*args, **kwargs):
    """
    git fetch; git checkout; git pull

    runs:
    git fetch
    git checkout {branch from settings or supplied}
    git pull

    :branch= sets the desired branch
    """

    branch = getattr(env.deploy_settings, 'BRANCH_NAME', 'master')
    print(cyan(f"Pulling from {branch}"))
    with cd(env.deploy_settings.DEPLOY_PATH):
        run('git fetch')
        run('git checkout {branch}')
        run('git pull')

@task
@surge_stack
def full_pull(*args, **kwargs):
    """
    fix_ownerships, pull, update_submodules, fix_ownerships

    runs:
    fix_ownerships
    pull
    update_submodules
    fix_ownerships

    :branch= sets the desired branch
    """
    
    fix_ownerships()
    pull()
    update_submodules()
    fix_ownerships()

@task
def update_submodules(*args, **kwargs):
    """
    Init and update the git submodules for the project

    runs:
    git submodule init
    git submodule update
    """
    with cd(env.deploy_settings.DEPLOY_PATH):
        print(cyan('Initializing submodules'))
        run('git submodule init')
        print("")

        print(cyan('Updating submodules'))
        run('git submodule update')
        print("")

@task
def fix_logfile_permissions(*args, **kwargs):
    """
    Sets the correct file permissions on the files in the LOG_PATH

    runs:
    chmod --preserve-root --changes a+r,ug+w -R LOGS_PATH
    """

    with cd(env.deploy_settings.DEPLOY_PATH):
        if getattr(env.deploy_settings, 'LOGS_PATH', False):
            print(cyan("Ensuring proper permissions on log files (-rw-rw-r--)"))
            sudo(f"chmod --preserve-root --changes a+r,ug+w -R {env.deploy_settings.LOGS_PATH}")
            print("")

@task
def install_requirements(*args, **kwargs):
    """
    Installs the project's requirements from the project's requirements.txt file
    into the project's activated virtual environment.

    runs:
    pip install -r requirements.txt
    """

    with cd(env.deploy_settings.DEPLOY_PATH):
        with prefix("source activate"):
            print(cyan("Installing from requirements.txt"))
            run("pip install -r requirements.txt")

@task
@needs_django
def collectstatic(*args, **kwargs):
    """
    Collect static assets for a Django project

    runs:
    manage.py collectstatic -v0 --noinput
    """

    print(cyan("Collecting static resources"))
    with cd(env.deploy_settings.DEPLOY_PATH):
        with prefix('source activate'):
            # Setting verbose to minimal outupt
            # We aren't going to prompt if we really want to collectstatic
            run("./manage.py collectstatic -v0 --noinput")

            # Get the settings module
            out = run("./manage.py diffsettings --all | grep SETTINGS_MODULE")
            split_sm = out.split("=")
            sm = None
            if len(split_sm) > 1:
                # Sometimes ./manage.py throws errors that end up in this output
                re_split_sm = re.split(r'(\n|\r|\r\n)', split_sm[1])[0]
                # Get the settings module
                m = re.search(r'[\'|\"].*?[\'|\"]', re_split_sm)
                sm = m.group().strip() if m else None

            # Get the STATIC_ROOT path
            srp = run(f"python -c 'from {sm} import STATIC_ROOT; print STATIC_ROOT'")
            static_root_path = srp if srp else 'collected-assets'

            # Touch the .less/.js files in STATIC_ROOT
            if exists(static_root_path):
                print(cyan('Touching *.less and *.js in {0}'.format(static_root_path)))
                # Exclude the _cache directory used by Compress
                run(f'find {static_root_path} \( -name "*.less" -or -name "*.js" \) -not -path "*/_cache*/*" -exec touch {{}} +')
                # Only fix the ownerships if collectstatic is called from the command line
                if not env.surge_stack:
                    sudo(f'chown {env.deploy_settings.CHOWN_TARGET} -R {static_root_path}')
                print("")
            else:
                print(red('Could not locate the STATIC_ROOT path for this project, skipping touches.\n'))



@task
@needs_django
@skip_if_not('SKIP_MIGRATE', False)
def run_migrations(*args, **kwargs):
    """
    Runs the Django manaagement command migrate for DJANGO_PROJECT=True

    runs:
    manage.py migrate
    """

    print(cyan("Running migrations"))
    with cd(env.deploy_settings.DEPLOY_PATH):
        with prefix('source activate'):
            run("./manage.py migrate")

    extra_migrations = getattr(env.deploy_settings, 'EXTRA_MIGRATE_FOR_DATABASES', [])
    if extra_migrations:
        print("")
        print(cyan("Running extra migrations"))
        with cd(env.deploy_settings.DEPLOY_PATH):
            with prefix('source activate'):
                for db in extra_migrations:
                    run(f"./manage.py migrate --database {db}")


@task
def run_extras(*args, **kwargs):
    """
    Runs any extra commands on HOST in EXTRA_COMMANDS list of the settings
    """

    with cd(env.deploy_settings.DEPLOY_PATH):
        with prefix('source activate'):
            for cmd in getattr(env.deploy_settings, 'EXTRA_COMMANDS', []):
                print(cyan(f'Extra:  {cmd}'))
                run(cmd)

@task
def restart_nginx(*args, **kwargs):
    """
    Restart the nginx service on HOST

    runs:
    sudo service nginx restart
    """

    print(cyan("Restarting Nginx"))
    
    if env.deploy_settings.OS_SERVICE_MANAGER == 'upstart':
        sudo('service nginx restart')
    elif env.deploy_settings.OS_SERVICE_MANAGER == 'systemd':
        sudo('systemctl restart nginx')
    else:
        raise ValueError(f'invalid OS_SERVICE_MANAGER setting: {env.deploy_settings.OS_SERVICE_MANAGER}')

@task
def bounce_services(*args, **kwargs):
    """
    Restarts the services on HOST from the BOUNCE_SERVICES list of the settings.

    runs:
    sudo service X restart (where X is each member of the BOUNCE_SERVICES list)

    :restart_nginx=True will also restart nginx
    """

    if not env.deploy_settings.BOUNCE_SERVICES:
        return None

    STATUS = {
        '+': 'Running',
        '-': 'Stopped/Waiting',
        '?': 'Unknown'
    }

    BSOIR = env.deploy_settings.BOUNCE_SERVICES_ONLY_IF_RUNNING
    if BSOIR:
        print(cyan("Bouncing processes...(BOUNCING_SERVICES_ONLY_IF_RUNNING)"))
    else:
        print(cyan("Bouncing processes..."))
    
    the_services = env.deploy_settings.BOUNCE_SERVICES
    print(cyan(the_services))
    
    there = []
    not_there = []
    for service in env.deploy_settings.BOUNCE_SERVICES:
        if env.deploy_settings.OS_SERVICE_MANAGER == 'upstart':
            status = sudo(f'service {service} status', quiet=True)
            
            if re.search(r'unrecognized service', status):
                not_there.append(service)
                continue
            
            if re.search(r'{} stop/waiting'.format(service), status):
                sglyph = '-'
            elif re.search(r'{} start/running'.format(service), status):
                sglyph = '+'
            else:
                sglyph = '?'
        elif env.deploy_settings.OS_SERVICE_MANAGER == 'systemd':
            status = sudo(f'systemctl status --full --no-pager {service}', quiet=True)
            
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
            raise ValueError(f'invalid OS_SERVICE_MANAGER setting: {env.deploy_settings.OS_SERVICE_MANAGER}')
        
        there.append((sglyph, service))

    for status, service in there:
        print(green("{0}: {1}".format(service, STATUS[status])))
        if status != '+' and BSOIR:
            print(red(f"{service} NOT bouncing"))
            continue
        
        if env.deploy_settings.OS_SERVICE_MANAGER == 'upstart':
            sudo(f'service {service} restart')
        elif env.deploy_settings.OS_SERVICE_MANAGER == 'systemd':
            sudo(f'systemctl restart {service}'))
        else:
            pass ###intentional - already checked

    for s in not_there:
        print(magenta(f"{s} not found on {env.deploy_settings.HOST}"))

    if bool_opt('restart_nginx', kwargs, default=False):
        restart_nginx()


@task
def services_status(*args, **kwargs):
    """
    Returns a list of the current status of the services on HOST from the BOUNCE_SERVICES list.

    runs:
    sudo service X status (where x is each member of the BOUNCE_SERVICES list)
    """

    for service in env.deploy_settings.BOUNCE_SERVICES:
        if env.deploy_settings.OS_SERVICE_MANAGER == 'upstart':
            status = sudo(f'service {service} status', quiet=True)
            hilight = green
            
            if re.search(f'{service} stop/waiting', status):
                hilight = red
            
            print(hilight(status))
        elif env.deploy_settings.OS_SERVICE_MANAGER == 'systemd':
            status = sudo(f'systemctl status --full --no-pager {service}', quiet=True)
            hilight = green
            
            if 'Active: inactive' in status or 'Active: failed' in status:
                hilight = red
            
            print(hilight(status))
        else:
            raise ValueError(f'invalid OS_SERVICE_MANAGER setting: {env.deploy_settings.OS_SERVICE_MANAGER}')

@task
def update_crontab(*args, **kwargs):
    """
    Replaces the current crontab for CRONTAB_OWNER on HOST with CRON_FILE

    runs:
    sudo crontab -u CRONTAB_OWNER CRON_FILE
    """

    cron_file = getattr(env.deploy_settings, 'CRON_FILE', None)
    crontab_owner = getattr(env.deploy_settings, 'CRONTAB_OWNER', None)
    
    if cron_file and crontab_owner:
        print(green("Updating crontab..."))
        sudo(f'crontab -u {crontab_owner} {cron_file}')
        print("")

@task
@needs_django
@skip_if_not('SKIP_SYNCDB', False)
def sync_db(*args, **kwargs):
    """
    Runs the Django manaagement command syncdb for DJANGO_PROJECT=True

    runs:
    manage sync_db
    """

    print(cyan("Sync DB"))
    with cd(env.deploy_settings.DEPLOY_PATH):
        with prefix('source activate'):
            run("./manage.py syncdb")

@task(default=True)
@surge_stack
def full_deploy(*args, **kwargs):
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


    print(green("Beginning deployment..."))
    print("")

    print(blue('Checking pre-requisites...'))

    is_local_clean()

    is_remote_clean()

    print("")
    print(green("Starting deployment..."))
    print("")

    print(green("Updating environment..."))

    fix_ownerships()

    pull()

    update_submodules()

    fix_logfile_permissions()

    install_requirements()

    collectstatic()

    sync_db()

    # if not bool_opt('skip_migrate', kwargs, default=False):
    #     run_migrations()
    run_migrations()

    run_extras()

    # post fix owners after checkout and other actions
    fix_ownerships()

    bounce_services()

    update_crontab()

    print(green("Done!"))


@task
def full_deploy_with_migrate(*args, **kwargs):
    # env.deploy_settings.SKIP_MIGRATE = False
    kwargs['SKIP_MIGRATE'] = False
    full_deploy(*args, **kwargs)
