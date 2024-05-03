# drzewo

sometimes when i'm walking, i see a tree i like. i'm not great at identifying trees by sight, but i'd like to be. this is a web application that will hopefully help with that.

not by taking pictures and using ML like iNaturalist or so, but a much more pedestrian approach of downloading datasets from city open data sites. toronto and ottawa to start because those are two cities i sometimes find myself walking and wondering about trees.


## From scratch

Fire up `psql` and run the commands in `drzewo.sql`

Install python3, make a venv if you want, run:
```
pip install -r requirements.txt
./load.py
```

