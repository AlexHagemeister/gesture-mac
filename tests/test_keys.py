from gesture_mac.output.keys import parse_chord


def test_modifier_only_chord():
    c = parse_chord("right-option")
    assert c.base is None
    assert c.modifiers == ((61, 0x80000 | 0x40),)


def test_combo_chord():
    c = parse_chord("cmd+shift+4")
    assert c.base == 21
    assert [k for k, _ in c.modifiers] == [55, 56]
    assert c.flags == 0x100000 | 0x08 | 0x20000 | 0x02


def test_aliases_and_case():
    assert parse_chord("Alt+Tab").modifiers[0][0] == 58
    assert parse_chord("F18").base == 79
