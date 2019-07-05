# AgrView: Agricultural Data Transformations #

## Introduction ##

This was a consulting project done for a remote sensing stealth startup working in the agricultural domain. The company collects a lot of aerial data about agricultural fields and hopes to leverage the data in machine learning models. Before this project, their data existed solely as raw text and image files stored in an S3 bucket. However, that data could not be easily queried. My project consisted of building out the company's initial data pipeline that would automatically validate, parse, and populate any data uploaded to their S3 bucket into a MySQL database for querying.

Because of confidentiality, many variable names have been obfuscated in the source code.

## Architecture ##

The data pipeline was developed using AWS Lambda and RDS. The reason for solely using managed services was because the company had a small team and wanted to take advantage of the convenience provided by managed services.

![Pipeline](https://user-images.githubusercontent.com/40527812/60703301-4d528180-9eb6-11e9-894c-0996a11ceda6.png)