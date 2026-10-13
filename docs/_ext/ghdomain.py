"""
Allows to link configuration values using :ghconf:`config_val`.
"""


def setup(app):
    app.add_crossref_type(
        directivename="ghconf",
        rolename="ghconf",
        indextemplate="single: configuration; %s",
    )
    return {"parallel_read_safe": True, "parallel_write_safe": True}
