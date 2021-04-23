# ETL-Project

# The Goal of this ETL was to compare NBA Team average salaries, age, and the temeprature of the city they play for.

# Data sources:
Salary data was pulled from a csv file found on Kaggle
Temperature data was pulled from OpenWeather API
Age data was pulled via webscraping basketballreference.com


# Importing Libraries
The below are the libraries used in the analysis
- numpy
- api_key
- requests

# Base Dataframe
- created a list of all NBA team names
- created a list of all the locations associated with the respective NBA team
- created a list of all the cities associated with the locations (will be used for API weather pull)

# Team Salary Data
- The csv file contained players salary for the 2017-18 NBA Season
- enables Pandas to read the csv file and created a dataframe
- used a numpy function to groupby the team names and mean of the salaries

# Team Age Data
- leveraged basketballreference.com to get 2017-18 player per minute stats
- the per minute stats table included team of the players and their respective age as well
- inspected the web url to get the HTML tags and id's from the table to pull the data
- after establishing a base url, ran function requests to get the data from the table based on the html tags
- only needed player name, team name, and age from the web page table
- created a dataframe and inspected it
- ran syntax to remove all duplicate player names so their age only shows up once
- the table pulled in had repeating headers for each new team. the syntax above removed all of them except the one indexed in row 20
- wrote syntax to remove the respective row column
- used a numpy function to groupby the team names and mean age of all the players on the team

# City Weather API
- leverged OpenWeather Historical API to get the average temp of the respective city
- baed on OpenWeather.com API instructions, pulled in city using the list created earlier
- wrote a for loop to collect the city name and the temp of the city 
- stored both values as a row in a dataframe

# Combining DataBases
- used Pandas left join to merge the dataframes
- dropped columns to show only location of the city assoicated with the team, team name, average salary, average age, and average city temp
