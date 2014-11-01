#! /usr/bin/env python
# encoding: utf-8


VERSION='1.0.0'
APPNAME='pdf_quench'


top = '.'
out = 'build'
src = 'src'
install = 'install'


def configure(conf):
  pass


def build(ctx):
  ctx.exec_command('mkdir -p install')
  if ctx.cmd == 'install':
    start_dir = ctx.path.find_dir(src)
    ctx.install_files('install/debian/usr/bin',
                      ctx.path.ant_glob(src + '/pdf_quench.py'),
                      cwd=start_dir,
                      relative_trick=False)
    start_dir = ctx.path.find_dir(top)
    ctx.install_files('install',
                      ctx.path.ant_glob('debian/**/*'),
                      cwd=start_dir,
                      relative_trick=True)


def chmod(ctx):
    print('Creating debian package ...')
    ctx.exec_command('chmod -R a+rX install/debian')
    ctx.exec_command(('mv install/debian/usr/bin/pdf_quench.py '
                      'install/debian/usr/bin/pdf_quench'))
    ctx.exec_command('chmod -R a+rx install/debian/usr/bin/pdf_quench')
    ctx.exec_command('chmod -R a+rx install/debian/DEBIAN/postinst')
    ctx.exec_command('chmod -R a+rx install/debian/DEBIAN/postrm')


def build_debian(ctx):
    print('Creating debian package ...')
    ctx.exec_command('fakeroot dpkg -b install/debian .')


def debian(ctx):
    import Options
    commands = ['configure', 'build', 'install', 'chmod', 'build_debian']
    Options.commands = commands + Options.commands
