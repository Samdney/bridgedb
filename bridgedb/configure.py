# -*- coding: utf-8 ; test-case-name: bridgedb.test.test_configure -*-
#
# This file is part of BridgeDB, a Tor bridge distribution system.
#
# :authors: please see the AUTHORS file for attributions
# :copyright: (c) 2013-2015, Isis Lovecruft
#             (c) 2013-2015, Matthew Finkel
#             (c) 2007-2015, Nick Mathewson
#             (c) 2007-2015, The Tor Project, Inc.
# :license: see LICENSE for licensing information

"""Utilities for dealing with configuration files for BridgeDB."""

import logging
import os

# Used to set the SUPPORTED_TRANSPORTS:
from bridgedb import strings


def loadConfig(configFile=None, configCls=None):
    """Load configuration settings on top of the current settings.

    All pathnames and filenames within settings in the ``configFile`` will be
    expanded, and their expanded values will be stored in the returned
    :class:`configuration <bridgedb.configure.Conf>` object.

    **Note:**

    On the strange-looking use of::

        exec compile(open(configFile).read(), '<string>', 'exec') in dict()

    in this function…

    The contents of the config file should be compiled first, and then passed
    to ``exec()`` -- not ``execfile()`` ! -- in order to get the contents of
    the config file to exist within the scope of the configuration dictionary.
    Otherwise, Python *will* default_ to executing the config file directly
    within the ``globals()`` scope.

    Additionally, it's roughly 20-30 times faster_ to use the ``compile()``
    builtin on a string (the contents of the file) before passing it to
    ``exec()``, than using ``execfile()`` directly on the file.

    .. _default: http://stackoverflow.com/q/17470193
    .. _faster: http://lucumr.pocoo.org/2011/2/1/exec-in-python/

    :ivar bool itsSafeToUseLogging: This is called in
        :func:`bridgedb.Main.run` before
        :func:`bridgedb.safelog.configureLogging`. When called from
        :func:`~bridgedb.Main.run`, the **configCls** parameter is not given,
        because that is the first time that a
        :class:`config <bridgedb.configure.Conf>` has been created. If a
        :class:`logging.Logger` is created in this function, then logging will
        not be correctly configured, therefore, if the **configCls** parameter
        is not given, then it's the first time this function has been called
        and it is therefore *not* safe to make calls to the logging module.
    :type configFile: :any:`str` or ``None``
    :param configFile: If given, the filename of the config file to load.
    :type configCls: :class:`bridgedb.configure.Conf` or ``None``
    :param configCls: The current configuration instance, if one already
        exists.
    :returns: A new :class:`configuration <bridgedb.configure.Conf>`, with the
        old settings as defaults, and the settings from the **configFile** (if
        given) overriding those defaults.
    """
    itsSafeToUseLogging = False
    configuration = {}

    if configCls:
        itsSafeToUseLogging = True
        oldConfig = configCls.__dict__
        configuration.update(**oldConfig)  # Load current settings
        logging.info("Reloading over in-memory configurations...")

    conffile = configFile
    if (configFile is None) and ('CONFIG_FILE' in configuration):
        conffile = configuration['CONFIG_FILE']

    if conffile is not None:
        if itsSafeToUseLogging:
            logging.info("Loading settings from config file: '%s'" % conffile)
        compiled = compile(open(conffile).read(), '<string>', 'exec')
        exec compiled in configuration

    if itsSafeToUseLogging:
        logging.debug("New configuration settings:")
        logging.debug("\n".join(["{0} = {1}".format(key, value)
                                 for key, value in configuration.items()
                                 if not key.startswith('_')]))

    # Create a :class:`Conf` from the settings stored within the local scope
    # of the ``configuration`` dictionary:
    config = Conf(**configuration)

    # We want to set the updated/expanded paths for files on the ``config``,
    # because the copy of this config, `state.config` is used later to compare
    # with a new :class:`Conf` instance, to see if there were any changes.
    #
    # See :meth:`bridgedb.persistent.State.useUpdatedSettings`.

    for attr in ["PROXY_LIST_FILES"]:
        setting = getattr(config, attr, None)
        if setting is None:  # pragma: no cover
            setattr(config, attr, []) # If they weren't set, make them lists
        else:
            setattr(config, attr, # If they were set, expand the paths:
                    [os.path.abspath(os.path.expanduser(f)) for f in setting])

    for attr in ["DB_FILE", "DB_LOG_FILE", "MASTER_KEY_FILE", "PIDFILE",
                 "ASSIGNMENTS_FILE", "HTTPS_CERT_FILE", "HTTPS_KEY_FILE",
                 "LOG_FILE", "COUNTRY_BLOCK_FILE",
                 "GIMP_CAPTCHA_DIR", "GIMP_CAPTCHA_HMAC_KEYFILE",
                 "GIMP_CAPTCHA_RSA_KEYFILE", "EMAIL_GPG_HOMEDIR",
                 "EMAIL_GPG_PASSPHRASE_FILE", "NO_DISTRIBUTION_FILE"]:
        setting = getattr(config, attr, None)
        if setting is None:
            setattr(config, attr, setting)
        else:
            setattr(config, attr, os.path.abspath(os.path.expanduser(setting)))

    for attr in ["HTTPS_ROTATION_PERIOD", "EMAIL_ROTATION_PERIOD"]:
        setting = getattr(config, attr, None) # Default to None
        setattr(config, attr, setting)

    for attr in ["IGNORE_NETWORKSTATUS", "CSP_ENABLED", "CSP_REPORT_ONLY",
                 "CSP_INCLUDE_SELF"]:
        setting = getattr(config, attr, True) # Default to True
        setattr(config, attr, setting)

    for attr in ["FORCE_PORTS", "FORCE_FLAGS", "NO_DISTRIBUTION_COUNTRIES"]:
        setting = getattr(config, attr, []) # Default to empty lists
        setattr(config, attr, setting)

    for attr in ["SUPPORTED_TRANSPORTS"]:
        setting = getattr(config, attr, {}) # Default to empty dicts
        setattr(config, attr, setting)

    # Set the SUPPORTED_TRANSPORTS to populate the webserver and email options:
    strings._setSupportedTransports(getattr(config, "SUPPORTED_TRANSPORTS", {}))
    strings._setDefaultTransport(getattr(config, "DEFAULT_TRANSPORT", ""))
    logging.info("Currently supported transports: %s" %
                 " ".join(strings._getSupportedTransports()))
    logging.info("Default transport: %s" % strings._getDefaultTransport())

    for domain in config.EMAIL_DOMAINS:
        config.EMAIL_DOMAIN_MAP[domain] = domain

    if conffile: # Store the pathname of the config file, if one was used
        config.CONFIG_FILE = os.path.abspath(os.path.expanduser(conffile))

    return config


class Conf(object):
    """A configuration object.  Holds unvalidated attributes."""
    def __init__(self, **attrs):
        for key, value in attrs.items():
            if key == key.upper():
                if not key.startswith('__'):
                    self.__dict__[key] = value
