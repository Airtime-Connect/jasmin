"""Real PostgreSQL role preflight against a disposable CI container only."""

import os

import psycopg

from jasmin.managers.testhub_c2_sovereign import C2SovereignError, _preflight


PORT = os.environ.get('ATC_C2_ROLE_PG_PORT', '')
if (os.environ.get('ATC_C2_ROLE_PG_DISPOSABLE') != '1'
        or not PORT.isdecimal() or not 1 <= int(PORT) <= 65535):
    raise SystemExit('refusing non-disposable PostgreSQL target')


def connect(user):
    return psycopg.connect(host='127.0.0.1', port=int(PORT),
                           dbname='testhub_c2_ci', user=user,
                           connect_timeout=2, autocommit=True)


def denied(factory, label):
    try:
        _preflight(factory)
    except C2SovereignError:
        return
    raise AssertionError(f'{label} passed C2 reader preflight')


with connect('testhub_admin') as admin:
    version = int(admin.execute("SELECT current_setting('server_version_num')").fetchone()[0])
    assert 180000 <= version < 190000, 'PostgreSQL 18 required'
    admin.execute('CREATE SCHEMA testhub')
    admin.execute('CREATE ROLE testhub_c2_ci_reader LOGIN NOSUPERUSER NOBYPASSRLS')
    for table in ('c2_principals', 'c2_leases', 'airtime_connectors',
                  'routes', 'witness_hops', 'verdicts', 'extra_relation'):
        admin.execute(f'CREATE TABLE testhub.{table} (id integer)')
    admin.execute('CREATE SEQUENCE testhub.extra_sequence')
    admin.execute('''CREATE FUNCTION testhub.issue_c2_lease(text,uuid,integer)
                     RETURNS void LANGUAGE plpgsql AS $$ BEGIN END $$''')
    admin.execute('''CREATE FUNCTION testhub.revoke_c2_lease(text)
                     RETURNS void LANGUAGE plpgsql AS $$ BEGIN END $$''')
    admin.execute('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA testhub FROM PUBLIC')
    admin.execute('GRANT USAGE ON SCHEMA testhub TO testhub_c2_ci_reader')
    admin.execute('''GRANT SELECT ON testhub.c2_principals, testhub.c2_leases,
                     testhub.airtime_connectors TO testhub_c2_ci_reader''')

reader = lambda: connect('testhub_c2_ci_reader')
_preflight(reader)

with connect('testhub_admin') as admin:
    admin.execute('GRANT SELECT ON testhub.extra_relation TO testhub_c2_ci_reader')
with reader() as connection:
    assert connection.execute(
        "SELECT has_table_privilege(current_user, 'testhub.extra_relation', 'SELECT')"
    ).fetchone() == (True,)
denied(reader, 'extra table SELECT')
with connect('testhub_admin') as admin:
    admin.execute('REVOKE SELECT ON testhub.extra_relation FROM testhub_c2_ci_reader')
_preflight(reader)

with connect('testhub_admin') as admin:
    admin.execute('GRANT SELECT(id) ON testhub.extra_relation TO testhub_c2_ci_reader')
denied(reader, 'extra column SELECT')
with connect('testhub_admin') as admin:
    admin.execute('REVOKE SELECT(id) ON testhub.extra_relation FROM testhub_c2_ci_reader')
_preflight(reader)

with connect('testhub_admin') as admin:
    admin.execute('GRANT USAGE ON SEQUENCE testhub.extra_sequence TO testhub_c2_ci_reader')
denied(reader, 'extra sequence USAGE')
with connect('testhub_admin') as admin:
    admin.execute('REVOKE USAGE ON SEQUENCE testhub.extra_sequence FROM testhub_c2_ci_reader')
_preflight(reader)

with connect('testhub_admin') as admin:
    admin.execute('CREATE ROLE testhub_c2_ci_elevated NOLOGIN')
    admin.execute('GRANT USAGE ON SCHEMA testhub TO testhub_c2_ci_elevated')
    admin.execute('GRANT SELECT ON testhub.routes TO testhub_c2_ci_elevated')
    admin.execute('''GRANT testhub_c2_ci_elevated TO testhub_c2_ci_reader
                     WITH INHERIT FALSE''')
with reader() as connection:
    assert connection.execute(
        "SELECT has_table_privilege(current_user, 'testhub.routes', 'SELECT')"
    ).fetchone() == (False,)
    connection.execute('SET ROLE testhub_c2_ci_elevated')
    assert connection.execute('SELECT count(*) FROM testhub.routes').fetchone() == (0,)
denied(reader, 'NOINHERIT membership with SET ROLE route read')
with connect('testhub_admin') as admin:
    admin.execute('REVOKE testhub_c2_ci_elevated FROM testhub_c2_ci_reader')
    admin.execute('REVOKE SELECT ON testhub.routes FROM testhub_c2_ci_elevated')
    admin.execute('REVOKE USAGE ON SCHEMA testhub FROM testhub_c2_ci_elevated')
    admin.execute('DROP ROLE testhub_c2_ci_elevated')
_preflight(reader)


def privileged_set_role_reader():
    connection = connect('testhub_admin')
    connection.execute('SET ROLE testhub_c2_ci_reader')
    return connection


denied(privileged_set_role_reader, 'privileged login switched to reader')
_preflight(reader)
print('PASS: disposable PostgreSQL 18 C2 role preflight grants and SET ROLE')
