"""Name bridging tests: normalization + ladder + ambiguity + unmatched (R3)."""

from ball_buddy.domain.naming import MatchReport, bridge, normalize, split_suffix

# -- normalization -------------------------------------------------------------


def test_normalize_strips_apostrophes_and_punctuation():
    assert normalize("Shaquille O'Neal") == "shaquille oneal"
    assert normalize("De'Anthony Melton") == "deanthony melton"


def test_normalize_casefolds_and_collapses_whitespace():
    assert normalize("  Nikola   JOKIC ") == "nikola jokic"
    assert normalize("Anthony Davis Jr.") == "anthony davis jr"


def test_split_suffix():
    assert split_suffix("anthony davis jr") == ("anthony davis", "jr")
    assert split_suffix("shaquille oneal") == ("shaquille oneal", "")
    assert split_suffix("wade iii") == ("wade", "iii")


# -- ladder --------------------------------------------------------------------


def test_alias_table_wins_over_everything():
    report = bridge(
        ["Nikola Jokic"],
        ["Jokic", "Nikola Joki"],  # pool has a near-miss, alias fixes it
        aliases={"Nikola Jokic": "Jokic"},
    )
    assert report.matched == {"Nikola Jokic": "Jokic"}
    assert report.ambiguous == {}
    assert report.unmatched == []


def test_alias_to_missing_pool_player_is_unmatched():
    report = bridge(["Nikola Jokic"], ["Someone Else"], aliases={"Nikola Jokic": "Ghost"})
    assert report.unmatched == [("Nikola Jokic", [])]
    assert report.matched == {}


def test_exact_normalized_hit():
    report = bridge(["Shaquille O'Neal"], ["Shaquille O'Neal", "Karl Malone"])
    assert report.matched == {"Shaquille O'Neal": "Shaquille O'Neal"}
    assert report.pool_unused == 1


def test_first_name_optional_containment():
    report = bridge(["Nikola Jokic"], ["Jokic"])
    assert report.matched == {"Nikola Jokic": "Jokic"}


def test_short_roster_name_matches_full_pool_name():
    report = bridge(["Jokic"], ["Nikola Jokic"])
    assert report.matched == {"Jokic": "Nikola Jokic"}


def test_suffix_must_agree():
    report = bridge(["Anthony Davis"], ["Anthony Davis Jr."])
    assert report.matched == {}
    assert [name for name, _ in report.unmatched] == ["Anthony Davis"]


def test_suffix_match_matches():
    report = bridge(["Anthony Davis Jr."], ["Anthony Davis Jr.", "Karl Malone"])
    assert report.matched == {"Anthony Davis Jr.": "Anthony Davis Jr."}


def test_ambiguity_never_auto_picked():
    # Two distinct pool entries both containing the roster name -> ambiguous.
    report = bridge(["Davis"], ["Anthony Davis", "Devin Davis"])
    assert report.matched == {}
    assert report.ambiguous == {"Davis": ["Anthony Davis", "Devin Davis"]}


def test_duplicate_exact_pool_entries_are_ambiguous():
    report = bridge(["Karl Malone"], ["Karl Malone", "Karl Malone"])
    assert report.ambiguous == {"Karl Malone": ["Karl Malone", "Karl Malone"]}


def test_unmatched_gets_last_name_suggestions():
    report = bridge(["Ghost Malone"], ["Nikola Jokic", "LeBron James", "Karl Malone Jr."])
    names, suggestions = report.unmatched[0]
    assert names == "Ghost Malone"
    assert suggestions == ["Karl Malone Jr."]
    assert report.problem_count == 1


def test_unmatched_without_suggestions():
    report = bridge(["Nobody Real"], ["Nikola Jokic"])
    assert report.unmatched == [("Nobody Real", [])]


def test_banner_text():
    report = MatchReport(unmatched=[("a", []), ("b", [])], ambiguous={"c": ["x"]})
    expected = "2 roster players unmatched · 1 ambiguous — add aliases.json entries to fix"
    assert report.banner_text() == expected
    assert MatchReport().banner_text() == ""


def test_pool_unused_counts_matched_only():
    report = bridge(["Jokic", "Nobody"], ["Jokic", "Karl Malone"])
    assert report.pool_unused == 1  # Karl Malone unused


def test_many_names_mixed():
    pool = ["Jokic", "LeBron James", "Anthony Davis Jr.", "Karl Malone"]
    roster = ["Nikola Jokic", "James", "Anthony Davis Jr.", "Shaquille O'Neal"]
    report = bridge(roster, pool)
    # "James" resolves uniquely to "LeBron James" (single containment hit).
    assert report.matched == {
        "Nikola Jokic": "Jokic",
        "James": "LeBron James",
        "Anthony Davis Jr.": "Anthony Davis Jr.",
    }
    assert report.ambiguous == {}
    assert ["Shaquille O'Neal"] == [name for name, _ in report.unmatched]
    assert report.unmatched[0][1] == []
