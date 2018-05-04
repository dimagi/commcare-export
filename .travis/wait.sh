#!/bin/bash

echo "Waiting MSSQL docker to launch on 1433..."

while ! nc -z localhost 1433; do
  sleep 0.1
done

echo "MSSQL launched"
