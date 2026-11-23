"""Smoke tests that the pinned native dependencies load on this platform."""


def test_planegcs_loads() -> None:
    import planegcs

    assert planegcs is not None


def test_ocp_loads() -> None:
    from OCP.Standard import Standard_Failure

    assert Standard_Failure is not None
