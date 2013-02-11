CommCare Export
===============

A Python library and command-line tools to generate customized exports from CommCareHQ.


Installation
------------

```
$ pip install commcare-export
```


Usage
-----

On the command-line:

```
$ commcare-export --commcare-hq=https://www.commcare-hq.org \
                  --username=your_username \
                  --domain=your_domain \
                  --version=0.1 \
                  --query '{"Map": {"source": {"Ref": "xform_es"}, "body": {"Ref": "form.report_date"}}}'}'
```

