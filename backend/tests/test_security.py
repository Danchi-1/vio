from vio_backend.security import (
    code_matches,
    compute_code_hash,
    compute_identity_hash,
    compute_session_token_hash,
    generate_otp_code,
    generate_session_token,
    mask_email,
    normalize_email,
)


def test_normalize_email_strips_and_lowercases():
    assert normalize_email("  SurnameTL.26@Student.FUNAAB.edu.ng  ") == "surnametl.26@student.funaab.edu.ng"


def test_identity_hash_is_deterministic_and_secret_dependent():
    email = "surnametl.26@student.funaab.edu.ng"
    assert compute_identity_hash("secret-a", email) == compute_identity_hash("secret-a", email)
    assert compute_identity_hash("secret-a", email) != compute_identity_hash("secret-b", email)


def test_identity_hash_ignores_case_and_surrounding_whitespace():
    assert compute_identity_hash("secret", "Student@Student.FUNAAB.edu.ng") == compute_identity_hash(
        "secret", "  student@student.funaab.edu.ng  "
    )


def test_generate_otp_code_is_six_digits():
    code = generate_otp_code()
    assert len(code) == 6
    assert code.isdigit()


def test_code_matches_round_trips_through_hash():
    code_hash = compute_code_hash("secret", "123456")
    assert code_matches("secret", "123456", code_hash)
    assert not code_matches("secret", "654321", code_hash)
    assert not code_matches("other-secret", "123456", code_hash)


def test_session_token_hash_round_trips():
    token = generate_session_token()
    token_hash = compute_session_token_hash("secret", token)
    assert compute_session_token_hash("secret", token) == token_hash
    assert compute_session_token_hash("secret", generate_session_token()) != token_hash


def test_generate_session_token_is_unique():
    assert generate_session_token() != generate_session_token()


def test_mask_email_hides_most_of_the_local_part():
    masked = mask_email("surnametl.26@student.funaab.edu.ng")
    assert masked.startswith("su")
    assert masked.endswith("@student.funaab.edu.ng")
    assert "surnametl.26" not in masked


def test_mask_email_handles_missing_domain():
    assert mask_email("not-an-email") == "***"
