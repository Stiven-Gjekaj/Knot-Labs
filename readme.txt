Knot Labs Unified Stack
=======================

A local-only simulation of a social media backend combining four subsystems:
Drift (ranking), Veil (categorization), Mesh (JSON storage), and Scribe (search).

Running
-------
```
python demo.py            # starts interactive REPL
python demo.py <cmd> ...  # run single command
python demo.py gui        # optional GUI if PySimpleGUI installed
```

Commands
--------
- labs USER                : create/set active user
- post POST_ID PATH        : create a post
- like/comment/share/gift POST_ID : engage with a post
- feed [N]                 : show top N posts
- search "query"          : search posts
- info post ID             : show post details
- info user ID             : show user details
- gen_samples N            : generate N sample users and posts
- users, posts, categories : listing helpers
- logout, whoami, help     : session utilities

Data is stored under ``data/`` using JSON files. The master list of categories
lives in ``data/mastercategories.txt`` and contains at least 200 labels.
