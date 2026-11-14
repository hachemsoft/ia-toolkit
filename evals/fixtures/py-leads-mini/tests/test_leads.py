from leads import leads_to_call


def test_leads_to_call():
    assert leads_to_call() == [1]
