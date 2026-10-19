from valutatrade_hub.core import usecases, utils

# чистим данные для чистого теста
utils.save_users([])
utils.save_portfolios([])

print("register:", usecases.register("alice", "1234"))
print("login:", usecases.login("alice", "1234"))
print("portfolio empty:", usecases.show_portfolio())

print("buy BTC:", usecases.buy("btc", 0.05))
print("buy USD:", usecases.buy("usd", 1500))
print("portfolio:", usecases.show_portfolio())

print("sell BTC:", usecases.sell("BTC", 0.01))
print("rate BTC->USD:", usecases.get_rate("BTC", "USD"))
print("rate USD->BTC:", usecases.get_rate("usd", "btc"))

usecases.logout()
try:
    usecases.buy("BTC", 0.01)
except ValueError as e:
    print("not logged ->", e)

try:
    usecases.register("alice", "1234")
except ValueError as e:
    print("dup username ->", e)

try:
    usecases.sell("ETH", 1)
except ValueError as e:
    print("no wallet ->", e)