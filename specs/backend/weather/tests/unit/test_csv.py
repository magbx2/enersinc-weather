from weather.services.csv_export import CSV_HEADER, neutralize_cell, render_row


def test_header_order_is_stable():
    assert CSV_HEADER == (
        "id",
        "city",
        "country_code",
        "temperature_c",
        "humidity_pct",
        "wind_speed_ms",
        "timestamp",
    )


def test_commas_quotes_and_newlines_are_quoted_per_rfc_4180():
    assert render_row(["Santiago, CL"]) == '"Santiago, CL"\r\n'
    assert render_row(['San "Juan"']) == '"San ""Juan"""\r\n'
    assert render_row(["line\nbreak"]) == '"line\nbreak"\r\n'


def test_formula_prefixes_are_neutralized():
    for value in ("=SUM(A1:A2)", "+1", "-1", "@cmd"):
        assert neutralize_cell(value) == f"'{value}"


def test_normal_cells_are_not_modified():
    assert neutralize_cell("Santiago") == "Santiago"
    assert render_row(["CL", 62]) == "CL,62\r\n"
