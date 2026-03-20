from core.token_manager import token_manager

# record = token_manager.get_tokens("20075487", "leodev901")
# print(record)
# print(record.access_token[:20] if record else None)
# print(record.refresh_token[:20] if record else None)
# print(record.access_token_expires_at if record else None)


token_manager.save_tokens(
    user_id="20075487",
    company_cd="leodev901",
    access_token="access-token-sample",
    refresh_token="refresh-token-sample",
    expires_in=3600,
)

record = token_manager.get_tokens("20075487", "leodev901")
print(record.user_id)
print(record.company_cd)
print(token_manager.is_access_token_valid("20075487", "leodev901"))

token_manager.save_oauth_state("state-123-random", "20075487", "leodev901")
state_record = token_manager.pop_oauth_state("state-123")
print(state_record.user_id)
print(token_manager.pop_oauth_state("state-123"))