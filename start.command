#!/bin/bash
cd ~/Projects/multitext
source venv/bin/activate
sleep 2 && open http://localhost:5050 &
python app.py
