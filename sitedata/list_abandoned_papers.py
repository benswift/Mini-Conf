import pandas as pd

all_papers = pd.read_csv("all_acmc2020_submissions.csv")
website_papers = pd.read_csv("papers.csv")

print("all papers")
print(all_papers.UID.count())

print("all accepted papers")
print(all_papers[all_papers.Decision == "ACCEPT"].UID.count())

print("website papers")
print(website_papers.UID.count())

print(all_papers[~all_papers.UID.isin(website_papers.UID) & (all_papers.Decision == "ACCEPT")])