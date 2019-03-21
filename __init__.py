from distutils.util import strtobool
import re
from functools import wraps
from fabric.api import env, local, abort, sudo, cd, run, task
from fabric.colors import green, red, blue, cyan, yellow, magenta
from fabric.context_managers import prefix
from fabric.decorators import hosts, with_settings
from fabric.contrib.files import exists
from pprint import pprint

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
#     ],
#     CRON_FILE='/deploy/intranet/confs/intranet/crontab.txt'
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
    OS_SERVICE_MANAGER='upstart',
    REQUIRE_REMOTE_CLEAN=True,
)

REQUIRED_SETTINGS = [
    'HOST',
    'USER',
    'GROUP',
    'DEPLOY_PATH',
]

class BASE_SETTINGS(object):
    def __init__(self, *args, **kwargs):
        self.kwargs = boold_up(kwargs)  # Keep track of original supplied settings
        self.settings = {}  # Keep a dictionary of all the settings
        self.settings.update(DEFAULT_SETTINGS)
        env['surge_stack'] = None  # Used by @surge_stack logic

        self.update(kwargs)

    def update(self, settings):
        new_settings = boold_up(settings)
        if 'CRONTAB_OWNER' not in self.kwargs:
            self.settings['CRONTAB_OWNER'] = new_settings.get('USER',
                                                              self.kwargs['USER'])
        self.CHOWN_TARGET = '{0}:{1}'.format(
            new_settings.get('USER', self.kwargs['USER']),
            new_settings.get('GROUP', self.kwargs['GROUP'])
        )

        self.settings['GIT_TREE'] = new_settings.get('DEPLOY_PATH',
                                                     self.kwargs['DEPLOY_PATH'])

        # Overide any of these automatically set settings from new_settings
        self.settings.update(new_settings)
        
        sreq = frozenset(REQUIRED_SETTINGS)
        sset = frozenset(self.settings.keys())
        missing = sreq.difference(sset)

        empty = filter(lambda k: type(self.settings[k]) not in [str, unicode] and self.settings[k] != '', REQUIRED_SETTINGS)

        if missing or empty:
            print red("Required settings are missing; {0}".format(', '.join(list(missing))))
            raise ValueError


        # Make them attributes
        self.__dict__.update(self.settings)


def boold_up(kwargs):
    """
    Will convert opt strings of True/False to python True/False.
    Will upcase keys.
    """
    fm = {'FALSE': False, 'TRUE': True}
    nd = {}
    for k, v in kwargs.items():
        try:
            nk = k.upper()
        except:
            nk = k
        try:
            nv = fm.get(v.upper(), v)
        except:
            nv = v
        nd[nk] = nv
    return nd

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

def needs_django(f):
    """
    A decorator on a task to ensure the task is not run if
    DJANGO_PROJECT = False
    """
    @wraps(f)
    def django_check(*args, **kwargs):
        if not getattr(env.deploy_settings, 'DJANGO_PROJECT', False):
            # If this was not called from another surge task then complain
            if not env.surge_stack:
                print red("This deployment is not configured as a DJANGO_PROJECT")
            return None
        return f(*args, **kwargs)
    return django_check

def surge_stack(f):
    """
    A surge_stack decorator on a task sets a 'surge_stack' attribute on the
    environment that is used to signal to other tasks that they were called
    as part of a sequence of other tasks and to not behave the same as they
    might if called alone.

    A surge_stack task can always override settings with it's kwargs
    """
    @wraps(f)
    def stash_surge_task(*args, **kwargs):
        env['surge_stack'] = f.__name__
        env.deploy_settings.update(kwargs)
        show_settings()
        return f(*args, **kwargs)

    return stash_surge_task

def skip_if_not(setting, what=True):
    """
    When called from a surge_stack task make sure the supplied setting is set
    to what (True or False) before running the decorated task.
    """
    def requires(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if env['surge_stack']:
                if not getattr(env.deploy_settings, setting, not what) == what:
                    return
            return f(*args, **kwargs)
        return wrapper
    return requires

def can_override_settings(f):
    """
    A task that when called command line can have its kwargs override the settings of the deploy
    """
    @wraps(f)
    def override(*args, **kwargs):
        if not env['surge_stack']:
            env.deploy_settings.update(kwargs)
        return f(*args, **kwargs)
    return override

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
    print "\n({0} {1} {2})\n".format(cyan('Configured'),
                                     green('Default'),
                                     magenta('Overridden Default'))
    for s in sorted(env.deploy_settings.settings.keys()):
        v = env.deploy_settings.settings[s]
        outcolor = cyan
        if s in DEFAULT_SETTINGS:
            outcolor = green if v == DEFAULT_SETTINGS[s] else magenta

        print outcolor("{0} = {1}".format(s, v))
        
@task
@skip_if_not('REQUIRE_CLEAN')
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
@skip_if_not('REQUIRE_REMOTE_CLEAN')
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
def fix_ownerships(*args, **kwargs):
    """
    Ensure the project files have the USER:GROUP ownership

    runs:
    chown USER:GROUP -R *
    chown USER:GROUP -R .git*
    chown USER:GROUP -R .env|env (if these exist)
    """

    with cd(env.deploy_settings.DEPLOY_PATH):
        print cyan('Fixing project ownerships')
        sudo('chown %s -R *' % env.deploy_settings.CHOWN_TARGET)
        sudo('chown %s -R .git*' % env.deploy_settings.CHOWN_TARGET)
        sudo('if [ -e .env ]; then chown %s -R .env; fi' % env.deploy_settings.CHOWN_TARGET)
        sudo('if [ -e env ]; then chown %s -R env; fi' % env.deploy_settings.CHOWN_TARGET)
        print ""

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
    print cyan("Pulling from {0}".format(branch))
    with cd(env.deploy_settings.DEPLOY_PATH):
        run('git fetch')
        run('git checkout {0}'.format(branch))
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
@needs_django
def collectstatic(*args, **kwargs):
    """
    Collect static assets for a Django project

    runs:
    manage.py collectstatic -v0 --noinput
    """

    print cyan("Collecting static resources")
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
            srp = run("python -c 'from {0} import STATIC_ROOT; print STATIC_ROOT'".format(sm))
            static_root_path = srp if srp else 'collected-assets'

            # Touch the .less/.js files in STATIC_ROOT
            if exists(static_root_path):
                print cyan('Touching *.less and *.js in {0}'.format(static_root_path))
                # Exclude the _cache directory used by Compress
                run('find {0} \( -name "*.less" -or -name "*.js" \) -not -path "*/_cache*/*" -exec touch {{}} +'.format(static_root_path))
                # Only fix the ownerships if collectstatic is called from the command line
                if not env.surge_stack:
                    sudo('chown {0} -R {1}'.format(env.deploy_settings.CHOWN_TARGET,
                                                   static_root_path))
                print ""
            else:
                print red('Could not locate the STATIC_ROOT path for this project, skipping touches.\n')



@task
@needs_django
@skip_if_not('SKIP_MIGRATE', False)
def run_migrations(*args, **kwargs):
    """
    Runs the Django manaagement command migrate for DJANGO_PROJECT=True

    runs:
    manage.py migrate
    """

    print cyan("Running migrations")
    with cd(env.deploy_settings.DEPLOY_PATH):
        with prefix('source activate'):
            run("./manage.py migrate")

    extra_migrations = getattr(env.deploy_settings, 'EXTRA_MIGRATE_FOR_DATABASES', [])
    if extra_migrations:
        print ""
        print cyan("Running extra migrations")
        with cd(env.deploy_settings.DEPLOY_PATH):
            with prefix('source activate'):
                for db in extra_migrations:
                    run("./manage.py migrate --database {}".format(db))


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
    
    if env.deploy_settings.OS_SERVICE_MANAGER == 'upstart':
        sudo('service nginx restart')
    elif env.deploy_settings.OS_SERVICE_MANAGER == 'systemd':
        sudo('systemctl restart nginx')
    else:
        raise ValueError('invalid OS_SERVICE_MANAGER setting: {}'.format(env.deploy_settings.OS_SERVICE_MANAGER))

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
    print cyan("Bouncing processes...{0}").format("(BOUNCING_SERVICES_ONLY_IF_RUNNING)" if BSOIR else "")
    the_services = env.deploy_settings.BOUNCE_SERVICES
    print cyan(the_services)
    
    there = []
    not_there = []
    for service in env.deploy_settings.BOUNCE_SERVICES:
        if env.deploy_settings.OS_SERVICE_MANAGER == 'upstart':
            status = sudo('service %s status' % service, quiet=True)
            
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
            status = sudo('systemctl status --full %s' % service, quiet=True)
            
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
            raise ValueError('invalid OS_SERVICE_MANAGER setting: {}'.format(env.deploy_settings.OS_SERVICE_MANAGER))
        
        there.append((sglyph, service))

    for status, service in there:
        print green("{0}: {1}".format(service, STATUS[status]))
        if status != '+' and BSOIR:
            print red("{} NOT bouncing".format(service))
            continue
        
        if env.deploy_settings.OS_SERVICE_MANAGER == 'upstart':
            sudo('service %s restart' % service)
        elif env.deploy_settings.OS_SERVICE_MANAGER == 'systemd':
            sudo('systemctl restart {}'.format(service))
        else:
            pass ###intentional - already checked

    for s in not_there:
        print magenta("{0} not found on {1}".format(s, env.deploy_settings.HOST))

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
            status = sudo('service %s status' % service, quiet=True)
            hilight = green
            
            if re.search(r'{} stop/waiting'.format(service), status):
                hilight = red
            
            print hilight(status)
        elif env.deploy_settings.OS_SERVICE_MANAGER == 'systemd':
            status = sudo('systemctl status --full {}'.format(service), quiet=True)
            hilight = green
            
            if 'Active: inactive' in status or 'Active: failed' in status:
                hilight = red
            
            print hilight(status)
        else:
            raise ValueError('invalid OS_SERVICE_MANAGER setting: {}'.format(env.deploy_settings.OS_SERVICE_MANAGER))

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
@needs_django
@skip_if_not('SKIP_SYNCDB', False)
def sync_db(*args, **kwargs):
    """
    Runs the Django manaagement command syncdb for DJANGO_PROJECT=True

    runs:
    manage sync_db
    """

    print cyan("Sync DB")
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


    print green("Beginning deployment...")
    print ""

    print blue('Checking pre-requisites...')

    is_local_clean()

    is_remote_clean()

    print ""
    print green("Starting deployment...")
    print ""

    print green("Updating environment...")

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

    print green("Done!")


@task
def full_deploy_with_migrate(*args, **kwargs):
    # env.deploy_settings.SKIP_MIGRATE = False
    kwargs['SKIP_MIGRATE'] = False
    full_deploy(*args, **kwargs)
