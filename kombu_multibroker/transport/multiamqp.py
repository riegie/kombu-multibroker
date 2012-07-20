import random
import string
import time

from kombu.transport import base, TRANSPORT_ALIASES
from kombu.transport.librabbitmq import Transport as AMQPTransport, ConnectionError
from kombu.log import get_logger

logger = get_logger("kombu.transport.multiamqp")

TRANSPORT_ALIASES["multiamqp"] = "kombu_multibroker.transport.multiamqp.Transport"

class NoHostsError(Exception):
    pass

class Transport(AMQPTransport):
    DOWN_HOST_RETRY_TIME = 30

    driver_name = "multiamqp"
    _down_hosts = {}

    def _mark_host_down(self, host):
        self._down_hosts[host] = time.time() + self.DOWN_HOST_RETRY_TIME

    def _check_host_down(self, host):
        expire_at = self._down_hosts.get(host)

        if expire_at:
            if time.time() < expire_at:
                return True
            else:
                del self._down_hosts[host]
                return False
        else:
            return False
        
    def establish_connection(self):
        """ Establish connection to one of the AMQP brokers. """
        
        conninfo = self.client
        
        for name, default_value in self.default_connection_params.items():
            if not getattr(conninfo, name, None):
                setattr(conninfo, name, default_value)

        # Supports multiple hosts separated by commas
        print conninfo.host
        hosts = string.split(conninfo.host, ",")
        random.shuffle(hosts)

        while True:
            if len(hosts) == 0:
                raise NoHostsError("Ran out of healthy hosts to talk to!")

            which_host = hosts.pop()

            if self._check_host_down(which_host):
                continue 

            try:
                conn = self.Connection(host = which_host,
                                       userid = conninfo.userid,
                                       password = conninfo.password,
                                       virtual_host = conninfo.virtual_host,
                                       login_method = conninfo.login_method,
                                       insist = conninfo.insist,
                                       ssl = conninfo.ssl,
                                       connect_timeout = conninfo.connect_timeout)
            except ConnectionError, e:
                self._mark_host_down(which_host)
                logger.warn("ConnectionError when connecting to broker: %s" % e)
                continue

            conn.client = self.client
            self.client.drain_events = conn.drain_events

            return conn
