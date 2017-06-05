from distutils.util import strtobool
import re
from fabric.api import env, local, abort, sudo, cd, run, task
from fabric.colors import green, red, blue, cyan, yellow, magenta
from fabric.context_managers import prefix
from fabric.decorators import hosts, with_settings


## Example settings
# USER = "intranet"
# GROUP = "intranet"
# HOST = 'ticketing.protectamerica.com'
#
# PROD_SETTINGS = deploy.BASE_SETTINGS(
#     HOST=HOST,
#     DEPLOY_PATH='/deploy/intranet',
#     USER=USER,
#     GROUP=GROUP,
#     BOUNCE_SERVICES=[
#         'intranet',
#         'intranet_celery',
#         'intranet_celerybeat',
#         'intranet_mail',
#         'intranet_snet',
#         'intranet_custidx'
#     ],
#     EXTRA_COMMANDS=[
#         'sudo cp crons/-etc-cron.d-restart_intranet_mail /etc/cron.d/restart_intranet_mail',
#         'sudo chown root:root /etc/cron.d/restart_intranet_mail',
#         # 'touch collected-assets/less/style.less',
#     ]
# )
#
# env.host_string = PROD_SETTINGS.HOST
# env.deploy_settings = PROD_SETTINGS
##


DEFAULT_SETTINGS = dict(
    REQUIRE_CLEAN=True,
    BRANCH_NAME='master',
    DJANGO_PROJECT=True,
    SKIP_SYNCDB=False,
    SKIP_MIGRATE=False,
    RESTART_NGINX=False,
    BOUNCE_SERVICES_ONLY_IF_RUNNING=False,
)

REQUIRED_SETTINGS = [
    'HOST',
    'USER',
    'GROUP',
    'DEPLOY_PATH',
]

class BASE_SETTINGS(object):
    def __init__(self, *args, **kwargs):
        sreq = frozenset(REQUIRED_SETTINGS)
        sset = frozenset(kwargs.keys())
        missing = sreq.difference(sset)
        if missing:
            print red("Required settings are missing; {0}".format(', '.join(list(missing))))
            raise ValueError
        self.kwargs = kwargs  # Keep track of supplied settings
        self.settings = {}  # Keep a dictionary of all the settings
        self.settings.update(DEFAULT_SETTINGS)
        self.settings['CRONTAB_OWNER'] = kwargs['USER']
        self.CHOWN_TARGET = kwargs['USER'] + ':' + kwargs['GROUP']
        self.settings['GIT_TREE'] = kwargs['DEPLOY_PATH']

        # Overide any of these automatically set settings from kwargs
        self.settings.update(kwargs)

        # Make them attributes
        self.__dict__.update(self.settings)


def bool_opt(opt, kwargs, default=False):
    """
    Will convert opt strings to python True/False, if it exists in kwargs.
    Or, will return what is in the deploy_settings if it exists there.
    Finally, will return the default if it doesn't exist in either.
    """

    opt = opt.lower()
    default = kwargs[opt] if opt in kwargs else getattr(env.deploy_settings, opt.upper(), default)
    if type(default) == str:
        return strtobool(default)
    return default


def django_check():
    if not getattr(env.deploy_settings, 'DJANGO_PROJECT', False):
        print red("This deployment is not configured as a DJANGO_PROJECT")
        return False
    return True

@task
def sudo_check():
    print cyan("Validating sudo.")
    result = sudo('echo "Got it!"')
    if result:
        return True
    else:
        print red("Could not obtain sudo!")
        return False

@task
def show_settings():
    print "\n({0} {1} {2})\n".format(cyan('Configured'), green('Default'), magenta('Overridden Default'))
    for s in sorted(env.deploy_settings.settings.keys()):
        v = env.deploy_settings.settings[s]
        outcolor = cyan
        if s in DEFAULT_SETTINGS:
            outcolor = green if v == DEFAULT_SETTINGS[s] else magenta

        print outcolor("{0} = {1}".format(s, v))
        
@task
def is_local_clean(*args, **kwargs):
    """
    Checks that the local git work area is clean or not

    runs:
    git status --porcelain
    """

    print cyan("Ensuring local working area is clean...")
    has_changes = local("git status --porcelain", capture=True)
    if has_changes:
        abort(red("Your working directory is not clean."))

    return not has_changes

@task
def is_remote_clean(*args, **kwargs):
    """
    Checks that the remote git work area is clean or not

    runs:
    git --work-tree=DEPLOY_PATH --git-dir=DEPLOY_PATH/.git status --porcelain
    """

    print cyan("Ensuring remote working area is clean...")
    git_cmd = "git --work-tree={0} --git-dir={0}/.git".format(env.deploy_settings.DEPLOY_PATH)
    has_changes = run(git_cmd + " status --porcelain")
    if has_changes:
        abort(red("Remote working directory is not clean."))

    return not has_changes

@task
def fix_project_owners(*args, **kwargs):
    """
    Ensure the project files have the USER:GROUP ownership

    runs:
    chown USER:GROUP -R *
    chown USER:GROUP -R .git*
    chown USER:GROUP -R .env|env (if these exist)
    """

    with cd(env.deploy_settings.DEPLOY_PATH):
        print cyan('Fixing project owners')
        sudo('chown %s -R *' % env.deploy_settings.CHOWN_TARGET)
        sudo('chown %s -R .git*' % env.deploy_settings.CHOWN_TARGET)
        sudo('if [ -e .env ]; then chown %s -R .env; fi' % env.deploy_settings.CHOWN_TARGET)
        sudo('if [ -e env ]; then chown %s -R env; fi' % env.deploy_settings.CHOWN_TARGET)
        print ""

@task
def pull(*args, **kwargs):
    """
    git fetch; git checkout; git pull

    runs:
    git fetch
    git checkout {branch from settings or supplied}
    git pull

    :branch= sets the desired branch
    """

    default_branch = getattr(env.deploy_settings, 'BRANCH_NAME', 'master')
    branch = kwargs.get('branch', default_branch)
    print cyan("Pulling from {0}".format(branch))
    with cd(env.deploy_settings.DEPLOY_PATH):
        run('git fetch')
        run('git checkout {0}'.format(branch))
        run('git pull')

@task
def full_pull(*args, **kwargs):
    """
    fix_project_owners, pull, update_submodules, fix_project_owners

    runs:
    fix_project_owners
    pull
    update_submodules
    fix_project_owners

    :branch= sets the desired branch
    """
    fix_project_owners()
    pull(**kwargs)
    update_submodules()
    fix_project_owners()

@task
def update_submodules(*args, **kwargs):
    """
    Init and update the git submodules for the project

    runs:
    git submodule init
    git submodule update
    """
    with cd(env.deploy_settings.DEPLOY_PATH):
            print cyan('Initializing submodules')
            run('git submodule init')
            print ""

            print cyan('Updating submodules')
            run('git submodule update')
            print ""

@task
def fix_logfile_permissions(*args, **kwargs):
    """
    Sets the correct file permissions on the files in the LOG_PATH

    runs:
    chmod --preserve-root --changes a+r,ug+w -R LOGS_PATH
    """

    with cd(env.deploy_settings.DEPLOY_PATH):
        if getattr(env.deploy_settings, 'LOGS_PATH', False):
            print cyan("Ensuring proper permissions on log files (-rw-rw-r--)")
            sudo("chmod --preserve-root --changes a+r,ug+w -R %s" % env.deploy_settings.LOGS_PATH)
            print ""

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
            print cyan("Installing from requirements.txt")
            run("pip install -r requirements.txt")

@task
def collect_static(*args, **kwargs):
    """
    Collect static assets for a Django project

    runs:
    manage.py collectstatic -v0 --noinput
    """

    print cyan("Collecting static resources")
    if not django_check():
        return
    with cd(env.deploy_settings.DEPLOY_PATH):
        with prefix('source activate'):
            # Setting verbose to minimal outupt
            # We aren't going to prompt if we really want to collectstatic
            run("./manage.py collectstatic -v0 --noinput")

@task
def run_migrations(*args, **kwargs):
    """
    Runs the Django manaagement command migrate for DJANGO_PROJECT=True

    runs:
    manage.py migrate
    """

    print cyan("Running migrations")
    if not django_check():
        return
    with cd(env.deploy_settings.DEPLOY_PATH):
        with prefix('source activate'):
            run("./manage.py migrate")

@task
def run_extras(*args, **kwargs):
    """
    Runs any extra commands on HOST in EXTRA_COMMANDS list of the settings
    """

    with cd(env.deploy_settings.DEPLOY_PATH):
        with prefix('source activate'):
            for cmd in getattr(env.deploy_settings, 'EXTRA_COMMANDS', []):
                print cyan('Extra:  ' + cmd)
                run(cmd)

@task
def restart_nginx(*args, **kwargs):
    """
    Restart the nginx service on HOST

    runs:
    sudo service nginx restart
    """

    print cyan("Restarting Nginx")
    sudo('service nginx restart')

@task
def bounce_services(*args, **kwargs):
    """
    Restarts the services on HOST from the BOUNCE_SERVICES list of the settings.

    runs:
    sudo service X restart (where X is each member of the BOUNCE_SERVICES list)

    :restart_nginx=True will also restart nginx
    """

    print cyan("Bouncing processes...")
    for service in env.deploy_settings.BOUNCE_SERVICES:
        if bool_opt("bounce_services_only_if_running", kwargs, default=False):
            status = sudo('service %s status' % service, quiet=True)
            if re.search(r'{} stop/waiting'.format(service), status):
                print red("{} NOT bouncing.".format(status))
                continue
        sudo('service %s restart' % service)

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
        status = sudo('service %s status' % service, quiet=True)
        hilight = green
        if re.search(r'{} stop/waiting'.format(service), status):
            hilight = red
        print hilight(status)

@task
def update_crontab(*args, **kwargs):
    """
    Replaces the current crontab for CRONTAB_OWNER on HOST with CRON_FILE

    runs:
    sudo crontab -u CRONTAB_OWNER CRON_FILE
    """

    if getattr(env.deploy_settings, 'CRON_FILE', None) and \
       getattr(env.deploy_settings, 'CRONTAB_OWNER', None):
        print green("Updating crontab...")
        sudo('crontab -u %s %s' % (env.deploy_settings.CRONTAB_OWNER,
                                   env.deploy_settings.CRON_FILE))
        print ""

@task
def sync_db(*args, **kwargs):
    """
    Runs the Django manaagement command syncdb for DJANGO_PROJECT=True

    runs:
    manage sync_db
    """

    print cyan("Sync DB")
    if not django_check():
        return
    with cd(env.deploy_settings.DEPLOY_PATH):
        with prefix('source activate'):
            run("./manage.py syncdb")

@task(default=True)
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
    fix_project_owners
    pull
    update_submodules
    fix_logfile_permissions
    install_requirements
    collect_static
    sync_db
    run_migrations
    run_extras
    fix_project_owners
    bounce_services
    update_crontab
    """

    show_settings()

    print green("Beginning deployment...")
    print ""

    print blue('Checking pre-requisites...')

    if bool_opt('require_clean', kwargs, default=True):
        is_local_clean()

    is_remote_clean()

    print ""
    print green("Starting deployment...")
    print ""

    print green("Updating environment...")

    fix_project_owners()

    pull(**kwargs)

    update_submodules()

    fix_logfile_permissions()

    install_requirements()

    collect_static()

    if not bool_opt('skip_syncdb', kwargs, default=False):
        sync_db()

    if not bool_opt('skip_migrate', kwargs, default=False):
        run_migrations()

    run_extras()

    # post fix owners after checkout and other actions
    fix_project_owners()

    bounce_services()

    update_crontab()

    print green("Done!")


@task
def full_deploy_with_migrate(*args, **kwargs):
    # env.deploy_settings.SKIP_MIGRATE = False
    full_deploy(*args, skip_migrate=False, **kwargs)
