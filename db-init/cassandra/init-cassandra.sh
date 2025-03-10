#!/bin/bash

# Wait for Cassandra to be ready
until cqlsh -e "describe keyspaces"; do
  echo "Cassandra is unavailable - sleeping"
  sleep 5
done

echo "Cassandra is up - executing CQL"

# Execute the CQL script
cqlsh -f /docker-entrypoint-initdb.d/cassandra.cql

echo "Cassandra initialization completed" 