This script pulls betting odd data for NHL games from various US sportsbooks using odds-api and calulates the implied win chance of each team.
Data is also pulled from my personal, private Elo rankings for the NHL teams and uses that data to calculate win odds for each team.
These two datasets are then compared and the games in which a team has a higher expected win % from my Elo data than from a given sportsbook, that game is added as a hit.
An email is then sent to a few people containing the full datasets and the list(s) of hits.

This code is very messy. This script was one of the first things I coded and it is a disaster.
I also adapted the code to pull the Google Sheets data, and use protonmail through selenium from web sources, however I can not seem to find the page I initially got it from.
If you recognize the code as yours, please let me know so I can credit you.
