import unipath
from fabric.api import *
from fabric.contrib import files

# Fab settings
env.hosts = ['ve.djangoproject.com']

# Deployment environment paths and settings and such.
env.deploy_base = unipath.Path('/home/www/djangoproject.com')
env.virtualenv = env.deploy_base
env.code_dir = env.deploy_base.child('src')
env.git_url = 'git://github.com/django/djangoproject.com.git'
env.default_deploy_ref = 'origin/master'

def full_deploy():
    """
    Full deploy: new code, update dependencies, migrate, and restart services.
    """
    deploy_code()
    update_dependencies()
    migrate()
    collectstatic()
    apache("restart")
    memcached("restart")

def deploy():
    """
    Quick deploy: new code and an in-place reload.
    """
    deploy_code()
    collectstatic()
    apache("reload")

def apache(cmd):
    """
    Manage the apache service. For example, `fab apache:restart`.
    """
    sudo('invoke-rc.d apache2 %s' % cmd)

def memcached(cmd):
    """
    Manage the memcached service. For example, `fab apache:restart`.
    """
    sudo('invoke-rc.d memcached %s' % cmd)

def deploy_code(ref=None):
    """
    Update code on the servers from Git.
    """
    ref = ref or env.default_deploy_ref
    puts("Deploying %s" % ref)
    if not files.exists(env.code_dir):
        sudo('git clone %s %s' % (env.git_url, env.code_dir))
    with cd(env.code_dir):
        sudo('git fetch && git reset --hard %s' % ref)

def update_dependencies():
    """
    Update dependencies in the virtualenv.
    """
    pip = env.virtualenv.child('bin', 'pip')
    reqs = env.code_dir.child('deploy-requirements.txt')
    sudo('%s -q install -U pip' % pip)
    sudo('%s -q install -r %s' % (pip, reqs))

def collectstatic():
    """
    Run collectstatic.
    """
    managepy('collectstatic --noinput')
    managepy('collectstatic --noinput', site='docs')

def migrate():
    """
    Run migrate/syncdb.
    """
    managepy('syncdb')
    managepy('migrate')
    managepy('syncdb', site='docs')
    managepy('migrate', site='docs')

def update_docs():
    """
    Force an update of the docs on the server.
    """
    managepy('update_docs -v2', site='docs')

def copy_db():
    """
    Copy the production DB locally for testing.
    """
    local('ssh %s pg_dump -U djangoproject -c djangoproject | psql djangoproject' % env.hosts[0])

def copy_docs():
    """
    Copy build docs locally for testing.
    """
    local('rsync -av --delete --exclude=.svn %s:%s/ /tmp/djangodocs/' %
            (env.hosts[0], env.deploy_base.child('docbuilds')))

def managepy(cmd, site='www'):
    """
    Helper: run a management command remotely.
    """
    assert site in ('docs', 'www')
    django_admin = env.virtualenv.child('bin', 'django-admin.py')
    sudo('%s %s --settings=django_%s.settings' % (django_admin, cmd, site))

def southify(app):
    """
    Southify an app remotely.

    This fakes the initial migration and then migrates forward. Use it the first
    time you do a deploy on app that's been newly southified.
    """
    managepy('migrate %s 0001 --fake' % app)
    managepy('migrate %s' % app)
