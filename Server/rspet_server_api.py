#!/usr/bin/env python2
# -*- coding: <UTF-8> -*-
"""RSPET Server's RESTful API."""
import argparse
from flask_cors import CORS, cross_origin
from flask import Flask, jsonify, abort, make_response, request, url_for
import rspet_server

__author__ = "Kolokotronis Panagiotis"
__copyright__ = "Copyright 2016, Kolokotronis Panagiotis"
__credits__ = ["Kolokotronis Panagiotis"]
__license__ = "MIT"
__version__ = "1.0"
__maintainer__ = "Kolokotronis Panagiotis"


APP = Flask(__name__)
CORS(APP)

# TODO:
# There's a handful of commands there is no point whatsoever in executing through here
# so in lack of a better solution (that will come in following versions) lets' do this.
EXCLUDED_FUNCTIONS = ["help", "List_Sel_Hosts", "List_Hosts", "Choose_Host", "Select",\
                        "ALL", "Exit", "Quit"]
PARSER = argparse.ArgumentParser(description='RSPET Server module.')
PARSER.add_argument("-c", "--clients", nargs=1, type=int, metavar='N',
                    help="Number of clients to accept.", default=[5])
PARSER.add_argument("--ip", nargs=1, type=str, metavar='IP',
                    help="IP to listen for incoming connections.",
                    default=["0.0.0.0"])
PARSER.add_argument("-p", "--port", nargs=1, type=int, metavar='PORT',
                    help="Port number to listen for incoming connections.",
                    default=[9000])
ARGS = PARSER.parse_args()
RSPET_API = rspet_server.API(ARGS.clients[0], ARGS.ip[0], ARGS.port[0])


def make_public_host(host, h_id):
    """Add full URI to host Dictionary"""
    new_host = host
    new_host['uri'] = url_for('get_host', host_id=h_id, _external=True)
    return new_host


def make_public_help(command, hlp_sntx):
    """Add full URI to help Dictionary"""
    new_command = hlp_sntx
    new_command['uri'] = url_for('command_help', command=command, _external=True)
    return new_command


def shutdown_server():
    """Shutdown server if running on werkzeug"""
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


@APP.errorhandler(404)
def not_found(error):
    """Return JSONified 404"""
    return make_response(jsonify({'error': 'Not found'}), 404)


@APP.errorhandler(400)
def bad_request(error):
    """Return JSONified 400"""
    return make_response(jsonify({'error': 'Bad request'}), 400)


@APP.route('/rspet/api/v1.0/hosts', methods=['GET'])
def get_hosts():
    """Return all hosts."""
    hosts = RSPET_API.get_hosts()
    return jsonify({'hosts': {h_id:make_public_host(hosts[h_id], h_id) for h_id in hosts}})


@APP.route('/rspet/api/v1.0/hosts/<string:host_id>', methods=['GET'])
def get_host(host_id):
    """Return specific host."""
    hosts = RSPET_API.get_hosts()
    try:
        host = hosts[host_id]
    except KeyError:
        abort(404)
    return jsonify(make_public_host(host, host_id))


@APP.route('/rspet/api/v1.0/hosts/<string:host_id>', methods=['POST'])
def run_cmd_host(host_id):
    """Execute host specific command."""
    if not request.json or 'command' not in request.json:
        abort(400)
    res = RSPET_API.select([host_id])
    if res["code"] != rspet_server.ReturnCodes.OK:
        abort(404)
    comm = request.json['command']
    if comm in EXCLUDED_FUNCTIONS:
        abort(400)
    try:
        args = request.json['args']
        for i, val in enumerate(args):
            args[i] = str(val)
    except KeyError:
        args = []
    res = RSPET_API.call_plugin(comm, args)
    #Unselect host. Maintain statelessness of RESTful.
    RSPET_API.select()
    return jsonify(res)


@APP.route('/rspet/api/v1.0/hosts', methods=['POST'])
def mul_cmd():
    """Execute command on multiple hosts."""
    if not request.json or 'command' not in request.json or 'hosts' not in request.json:
        abort(400)
    hosts = request.json['hosts']
    res = RSPET_API.select(hosts)
    if res["code"] != rspet_server.ReturnCodes.OK:
        abort(404)
    comm = request.json['command']
    if comm in EXCLUDED_FUNCTIONS:
        abort(400)
    try:
        args = request.json['args']
        for i, val in enumerate(args):
            args[i] = str(val)
    except KeyError:
        args = []
    res = RSPET_API.call_plugin(comm, args)
    #Unselect host. Maintain statelessness of RESTful.
    RSPET_API.select()
    return jsonify(res)


@APP.route('/rspet/api/v1.0', methods=['POST'])
def run_cmd():
    """Execute general (non-host specific) command."""
    if not request.json or 'command' not in request.json:
        abort(400)
    comm = request.json['command']
    if comm in EXCLUDED_FUNCTIONS:
        abort(400)
    try:
        args = request.json['args']
        for i, val in enumerate(args):
            args[i] = str(val)
    except KeyError:
        args = []
    ret = RSPET_API.call_plugin(comm, args)
    if ret['code'] == rspet_server.ReturnCodes.OK:
        http_code = 200
    else:
        http_code = 404
    return make_response(jsonify(ret), http_code)


@APP.route('/rspet/api/v1.0', methods=['GET'])
def sitemap():
    """Return API map."""
    rat = []
    for rule in APP.url_map.iter_rules():
        uri = str(rule)
        if 'static' in uri:
            continue
        rat.append({'uri':uri, 'doc':globals()[rule.endpoint].__doc__,\
                    'methods':list(rule.methods)})
    return jsonify(rat)


@APP.route('/rspet/api/v1.0/help', methods=['GET'])
def general_help():
    """Return general help."""
    hlp_sntx = RSPET_API.help()
    for hlp in EXCLUDED_FUNCTIONS:
        if hlp in hlp_sntx:
            hlp_sntx.pop(hlp)
    return jsonify({'commands': {command:make_public_help(command, hlp_sntx[command])\
                    for command in hlp_sntx}})


@APP.route('/rspet/api/v1.0/help/<string:command>', methods=['GET'])
def command_help(command):
    """Return command specific help."""
    hlp_sntx = RSPET_API.help()
    if command in EXCLUDED_FUNCTIONS:
        abort(400)
    try:
        help_cm = hlp_sntx[command]
    except KeyError:
        abort(404)
    return jsonify(make_public_help(command, help_cm))


@APP.route('/rspet/api/v1.0/plugins/available', methods=['GET'])
def available_plugins():
    """Low-level interaction. Get available plugins."""
    server = RSPET_API.get_server()
    avail_plug = server.available_plugins()
    return jsonify(avail_plug)


@APP.route('/rspet/api/v1.0/plugins/installed', methods=['GET'])
def installed_plugins():
    """Low-level interaction. Get installed plugins."""
    server = RSPET_API.get_server()
    inst_plug = server.installed_plugins()
    return jsonify(inst_plug)


@APP.route('/rspet/api/v1.0/plugins/loaded', methods=['GET'])
def loaded_plugins():
    """Low-level interaction. Get loaded plugins."""
    server = RSPET_API.get_server()
    load_plug = server.loaded_plugins()
    return jsonify(load_plug)


@APP.route('/rspet/api/v1.0/plugins/install', methods=['POST'])
def install_plugin():
    """Low-level interaction. Install plugins."""
    if not request.json or 'plugins' not in request.json:
        abort(400)
    plugins = request.json['plugins']
    server = RSPET_API.get_server()
    for plugin in plugins:
        server.install_plugin(plugin)
    return make_response('', 204)


@APP.route('/rspet/api/v1.0/plugins/load', methods=['POST'])
def load_plugin():
    """Low-level interaction. Load plugins."""
    if not request.json or 'plugins' not in request.json:
        abort(400)
    plugins = request.json['plugins']
    server = RSPET_API.get_server()
    for plugin in plugins:
        server.load_plugin(plugin)
    return make_response('', 204)


@APP.route('/rspet/api/v1.0/refresh', methods=['GET'])
def refresh():
    """Refresh server. Check for lost hosts."""
    RSPET_API.refresh()
    return make_response('', 204)


@APP.route('/rspet/api/v1.0/quit', methods=['GET'])
def shutdown():
    """Shutdown the Server."""
    RSPET_API.quit()
    shutdown_server()
    print 'Server shutting down...'
    return make_response('', 204)


if __name__ == '__main__':
    APP.run(debug=False, threaded=True)
