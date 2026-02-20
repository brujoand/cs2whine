from console_log import ConsoleLogParser


def test_parse_damage_given():
    print("=== Test: Parse damage given ===")
    parser = ConsoleLogParser("/dev/null")
    parser._parse(
        'Damage Given to "Player1" - 98 in 4 hits\n'
        'Damage Given to "Player2" - 27 in 1 hit\n'
        "Some other line\n"
    )
    report = parser.take_report()
    assert report is not None, "Expected a report"
    assert len(report.given) == 2
    assert report.given[0] == ("Player1", 98, 4)
    assert report.given[1] == ("Player2", 27, 1)
    print("  PASS")


def test_parse_damage_taken():
    print("\n=== Test: Parse damage taken ===")
    parser = ConsoleLogParser("/dev/null")
    parser._parse(
        'Damage Taken from "Enemy1" - 42 in 2 hits\n'
        'Damage Taken from "Enemy2" - 100 in 1 hit\n'
        "Round end\n"
    )
    report = parser.take_report()
    assert report is not None
    assert len(report.taken) == 2
    assert report.taken[0] == ("Enemy1", 42, 2)
    assert report.taken[1] == ("Enemy2", 100, 1)
    print("  PASS")


def test_mixed_damage():
    print("\n=== Test: Mixed damage given and taken ===")
    parser = ConsoleLogParser("/dev/null")
    parser._parse(
        'Damage Given to "A" - 50 in 2 hits\n'
        'Damage Taken from "B" - 30 in 1 hit\n'
        'Damage Given to "C" - 100 in 1 hit\n'
        "---\n"
    )
    report = parser.take_report()
    assert report is not None
    assert len(report.given) == 2
    assert len(report.taken) == 1
    print("  PASS")


def test_take_report_clears():
    print("\n=== Test: take_report clears pending ===")
    parser = ConsoleLogParser("/dev/null")
    parser._parse('Damage Given to "X" - 10 in 1 hit\nend\n')
    r1 = parser.take_report()
    assert r1 is not None
    r2 = parser.take_report()
    assert r2 is None, "Second take should be None"
    print("  PASS")


def test_no_damage_lines():
    print("\n=== Test: No damage lines ===")
    parser = ConsoleLogParser("/dev/null")
    parser._parse("Just some random console output\nAnother line\n")
    report = parser.take_report()
    assert report is None
    print("  PASS")


if __name__ == "__main__":
    test_parse_damage_given()
    test_parse_damage_taken()
    test_mixed_damage()
    test_take_report_clears()
    test_no_damage_lines()
