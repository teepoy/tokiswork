"""Small supervised contrastive learning demo package."""


def run_demo(*args, **kwargs):
    from .demo import run_demo as _run_demo

    return _run_demo(*args, **kwargs)


def supervised_contrastive_loss(*args, **kwargs):
    from .demo import supervised_contrastive_loss as _loss

    return _loss(*args, **kwargs)


__all__ = ["run_demo", "supervised_contrastive_loss"]
