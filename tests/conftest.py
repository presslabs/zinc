def pytest_xdist_setupnodes(config, specs):
    config.option.verbose = 0
