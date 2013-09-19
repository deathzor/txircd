from twisted.internet import reactor, ssl
from twisted.python import log
from txircd.ircd import IRCD, default_options
from txircd.server import ServerFactory
from OpenSSL import SSL
import yaml, collections, sys, signal

# A direct copy of DefaultOpenSSLContext factory as of Twisted 12.2.0
# The only difference is using ctx.use_certificate_chain_file instead of ctx.use_certificate_file
# This code remains unchanged in the newer Twisted 13.0.0
class ChainedOpenSSLContextFactory(ssl.DefaultOpenSSLContextFactory):
    def cacheContext(self):
        if self._context is None:
            ctx = self._contextFactory(self.sslmethod)
            ctx.set_options(SSL.OP_NO_SSLv2)
            ctx.use_certificate_chain_file(self.certificateFileName)
            ctx.use_privatekey_file(self.privateKeyFileName)
            self._context = ctx

def createHangupHandler(ircd):
    return lambda signal, stack: ircd.rehash()

if __name__ == "__main__":
    # Copy the defaults
    options = default_options.copy()
    # Parse command line
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="txircd.yaml")
    parser.add_argument("--irc-port", dest="ircport", type=int)
    parser.add_argument("--ssl-port", dest="sslport", type=int)
    parser.add_argument("--name")
    parser.add_argument("--motd")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true")
    parser.add_argument("-l", "--log-file", dest="log_file", type=argparse.FileType('a'), default=sys.stdout)
    parser.add_argument("--client-timeout", dest="client_timeout", type=int)
    args = parser.parse_args()
    # Load config file
    try:
        with open(args.config) as f:
            options.update(yaml.safe_load(f))
    except:
        pass # Oh well
    # Update options with command line values
    if args.ircport:
        options["server_port_tcp"] = args.ircport
    if args.sslport:
        options["server_port_ssl"] = args.sslport
    if args.name:
        options["network_name"] = args.name
    if args.motd:
        options["server_motd"] = args.motd
    if args.client_timeout:
        options["client_timeout"] = args.client_timeout
    # Finally launch the app with the options
    if options["app_verbose"] or args.verbose:
        log.startLogging(args.log_file)
    ssl_cert = ChainedOpenSSLContextFactory(options["app_ssl_key"],options["app_ssl_pem"])
    ssl_cert.getContext().set_verify(SSL.VERIFY_PEER, lambda connection, x509, errnum, errdepth, ok: True) # We can ignore the validity of certs to get what we need
    ircd = IRCD(args.config, options, ssl_cert)
    serverlink_factory = ServerFactory(ircd)
    if options["server_port_tcp"]:
        if isinstance(options["server_port_tcp"], collections.Sequence):
            for port in options["server_port_tcp"]:
                try:
                    reactor.listenTCP(int(port), ircd, interface="::")
                except:
                    pass # Wasn't a number
        else:
            try:
                reactor.listenTCP(int(options["server_port_tcp"]), ircd, interface="::")
            except:
                pass # Wasn't a number
    if options["server_port_ssl"]:
        if isinstance(options["server_port_ssl"], collections.Sequence):
            for port in options["server_port_ssl"]:
                try:
                    reactor.listenSSL(int(port), ircd, ssl_cert, interface="::")
                except:
                    pass # Wasn't a number
        else:
            try:
                reactor.listenSSL(int(options["server_port_ssl"]), ircd, ssl_cert, interface="::")
            except:
                pass # Wasn't a number
    if options["server_port_web"]:
        if isinstance(options["server_port_web"], collections.Sequence):
            for port in options["server_port_web"]:
                try:
                    reactor.listenSSL(int(port), SockJSFactory(ircd), ssl_cert, interface="::")
                except:
                    pass # Wasn't a number
        else:
            try:
                reactor.listenSSL(int(options["server_port_web"]), SockJSFactory(ircd), ssl_cert, interface="::")
            except:
                pass # Wasn't a number
    if options["serverlink_port_tcp"]:
        if isinstance(options["serverlink_port_tcp"], collections.Sequence):
            for port in options["serverlink_port_tcp"]:
                try:
                    reactor.listenTCP(int(port), serverlink_factory, interface="::")
                except:
                    pass
        else:
            try:
                reactor.listenTCP(int(options["serverlink_port_tcp"]), serverlink_factory, interface="::")
            except:
                pass
    if options["serverlink_port_ssl"]:
        if isinstance(options["serverlink_port_ssl"], collections.Sequence):
            for port in options["serverlink_port_ssl"]:
                try:
                    reactor.listenSSL(int(port), serverlink_factory, ssl_cert, interface="::")
                except:
                    pass
        else:
            try:
                reactor.listenSSL(int(options["serverlink_port_ssl"]), serverlink_factory, ssl_cert, interface="::")
            except:
                pass
    # Bind SIGHUP to rehash
    signal.signal(signal.SIGHUP, createHangupHandler(ircd))
    # And start up the reactor
    reactor.run()