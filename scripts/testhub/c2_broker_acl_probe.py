"""AMQP 0-9-1 probe for a disposable RabbitMQ C2 topic-permission fixture."""

import argparse

import pika


VHOST = 'atc-c2-local'
EXCHANGE = 'messaging'
ROUTE = 'submit.sm.synthetic-cid-a'
QUEUE = ROUTE


def open_channel(port, user, password):
    parameters = pika.ConnectionParameters(
        host='127.0.0.1', port=port, virtual_host=VHOST,
        credentials=pika.PlainCredentials(user, password),
        socket_timeout=3, connection_attempts=1,
    )
    connection = pika.BlockingConnection(parameters)
    return connection, connection.channel()


def publish(port, user, password, exchange, routing_key, body):
    connection, channel = open_channel(port, user, password)
    try:
        channel.confirm_delivery()
        channel.basic_publish(exchange=exchange, routing_key=routing_key, body=body)
        connection.process_data_events(time_limit=0.2)
    finally:
        if connection.is_open:
            connection.close()


def expect_denied(port, exchange, routing_key):
    try:
        publish(port, 'c2_untrusted', 'local-only-untrusted',
                exchange, routing_key, b'denied')
    except pika.exceptions.ChannelClosedByBroker as error:
        if error.reply_code != 403:
            raise AssertionError(f'unexpected broker denial: {error.reply_code}') from error
        return
    raise AssertionError(f'untrusted publisher reached {exchange or "default"}:{routing_key}')


def consume_expected(channel, expected):
    method, _, body = channel.basic_get(queue=QUEUE, auto_ack=True)
    if method is None or body != expected:
        raise AssertionError(f'expected synthetic message was not delivered: {expected!r}')


def main(port):
    internal, channel = open_channel(port, 'c2_internal', 'local-only-internal')
    try:
        channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic')
        channel.queue_declare(queue=QUEUE, durable=False)
        channel.queue_bind(queue=QUEUE, exchange=EXCHANGE, routing_key=ROUTE)
        channel.confirm_delivery()
        channel.basic_publish(exchange=EXCHANGE, routing_key=ROUTE, body=b'internal')
        consume_expected(channel, b'internal')

        # Resource write permission alone is insufficient: without a topic
        # permission entry RabbitMQ accepts the protected routing key.
        publish(port, 'c2_unscoped', 'local-only-unscoped',
                EXCHANGE, ROUTE, b'unscoped')
        consume_expected(channel, b'unscoped')
    finally:
        internal.close()

    publish(port, 'c2_untrusted', 'local-only-untrusted',
            EXCHANGE, 'sandbox.ping', b'allowed')
    expect_denied(port, EXCHANGE, ROUTE)
    expect_denied(port, '', ROUTE)
    print('PASS: unscoped topic route accepted (red); scoped sandbox allowed; '
          'protected topic and default-exchange publishes denied 403 (green)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('local_port', type=int)
    arguments = parser.parse_args()
    if not 1 <= arguments.local_port <= 65535:
        raise SystemExit('invalid local port')
    main(arguments.local_port)
