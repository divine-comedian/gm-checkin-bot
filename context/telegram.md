# telegram support 

- bot also has the ability to send messages to a particular telegram user
- telegram user can be added to existing group of either developers or product managers
- admin can add or remove telegram users from groups
- admin can trigger a check-in for a given group, the message arrives to the given telegram user
- when admin triggers check-in message the bot returns a delivery report for each discord and telegram user, confirming that the message was successfully received by each user
- the check-in response from the telegram user is recorded into the google sheet, copying the same functionality defined in bot.py for discord.