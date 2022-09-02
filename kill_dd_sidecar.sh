#!/bin/bash
agent_pids=$(pgrep agent)
for pid in $agent_pids; 
do
    kill -INT $pid
done
