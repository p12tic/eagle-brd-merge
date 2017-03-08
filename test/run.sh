#!/bin/bash
../merge.py -h

../merge.py test_out.brd \
			test_in.brd	 \
			test_in.brd --offx 100mm --rotation 90 \
			test_in.brd -x 100mm -y 100mm -r 180 \
			test_in.brd --offy 100mm --rotation 270
