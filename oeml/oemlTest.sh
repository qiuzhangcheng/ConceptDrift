#!/bin/bash

# Execute one test OEML experiment

mkdir ./exp/test/ 2> /dev/null
./oeml.sh ../../../cedar-brt-drift/ ./exp/test/ 3 1 1 extDrift T http://cedar.example.org/ns#hisco http://www.w3.org/2004/02/skos/core#broader http://cedar.example.org/ns#occupation

exit 0