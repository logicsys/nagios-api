from distutils.core import setup
import os

version = os.environ.get("VERSION", "1.2.2")

setup(name='nagios-api',
      version=version,
      description='Control nagios using an API',
      author='Mark Smith',
      author_email='mark@qq.is',
      license='BSD New (3-clause) License',
      long_description=open('README.md').read(),
      url='https://github.com/xb95/nagios-api',
      packages=['nagios'],
      scripts=['nagios-cli', 'nagios-api'],
      install_requires=[
        'flask>=2.0',
        'requests>=2.20',
        'waitress>=2.0',
      ]
     )
