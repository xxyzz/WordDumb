#!/usr/bin/env python3

import argparse
import sqlite3

import redis

'''
Save X-Ray strings to redis
'''

parser = argparse.ArgumentParser()
parser.add_argument("x_ray_file", help="path of XRAY.entities.ASIN.asc file.")
args = parser.parse_args()

x_ray_conn = sqlite3.connect(args.x_ray_file)
r = redis.Redis()
key = 'x_ray_string'
r.delete(key)

for data in x_ray_conn.execute('SELECT * FROM string'):
    r.rpush(key, '|'.join(map(str, data)))

x_ray_conn.close()
r.shutdown(save=True)
