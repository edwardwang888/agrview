# AgrView: Agricultural Data Transformations #

## Introduction ##

This was a consulting project done for a remote sensing stealth startup working in the agricultural domain. The company collects a lot of aerial data about agricultural fields and hopes to leverage the data in machine learning models. Before this project, their data existed solely as raw text and image files stored in an S3 bucket. However, that data could not be easily queried. My project consisted of building out the company's initial data pipeline that would automatically validate, parse, and populate any data uploaded to their S3 bucket into a MySQL database.

Because of confidentiality, many variable names have been obfuscated in the source code.

## Details ##

Every time one batch of data is collected, up to 30,000 files are uploaded to the S3 bucket. However, the ETL (validation and parsing) pipeline does not actually need to process all of the files because many of the files are imaging data that are not well-suited for database storage. Instead, the pipeline retrieves the raw text files that require parsing, and processes those files. The data from the text files is populated into the database, along with a path to the location where the image files are stored. The number of image files is counted to verify that it is consistent with the duration of data collection, but the contents of the image files are not examined since that is best done manually in this particular case.

## Architecture ##

The data pipeline was developed using AWS Lambda and RDS. AWS Lambda was used because the ETL process, as described above, was not resource-intensive and could fit reasonably within the memory and time limits of AWS Lambda. Addtionally, the serverless architecture of AWS Lambda meant that I did not need to worry about EC2 instance configuration. Had the ETL process been more resource-intensive, however, AWS Batch would have been the next alternative. A step function was used to orchestrate the workflow of the ETL process.

Although open source technologies were considered, managed services were ultimately chosen because the company had a small team and wanted to take advantage of the convenience provided by managed services.

![Pipeline](https://user-images.githubusercontent.com/40527812/60743192-61819780-9f25-11e9-8bc4-16bbb758fe1d.png)

## Engineering Challenges ##

An interesting challenge arose when trying to decide how best to trigger the ETL process from S3. Even though up to 30,000 files could be uploaded per batch, the ETL process should not be triggered 30,000 times since the process was only to be run once per batch. In the ideal case, the ETL process would only be triggered after all files had finished uploading, but it was hard to determine when the files would finish uploading unless they were, say, uploaded in a particular order.

Ultimately, these two alternatives were considered:

1. Trigger the ETL process *once* per batch when the first file was uploaded. This meant that we needed to determine when the files had finished uploading. A simple way to do this was to poll the S3 bucket every few hours to check the timestamps of the files. When no addtional files had been uploaded for a certain amount of time, we could assume that the files had finished uploading and run the ETL process.

2. Use AWS CloudTrail to maintain a log of all file uploads to the S3 bucket. (Whenever a file is uploaded, CloudTrail creates a log file in a separate S3 bucket.) Once a day, check the logs to determine if any new batches had been uploaded. If so, then check the timestamp for the last uploaded file; if this was over a certain amount of time, assume that the files had finished uploading and run the ETL process. If not, wait a few hours and check again.

### Comparison ###

* The primary difference between these approaches was that the first was event-driven while the second was a batch job.
* The benefit of the event-driven approach was that additional storage was not required for the storage of log files and it was simple to implement. However, the drawback was that there would be more waiting time while files were uploading.
* The batch approach would, on average, incur less waiting time since it would only run once per day. However, it required allocating additional S3 storage for the log files. Additionally, this approach introduced other complexities, such as: what if multiple batches were uploaded on the same day? We would then need to keep track of all the batches uploaded that day. The likelihood for errors would be higher in this approach because of these complexities.
* The number of files that needed to be examined was similar in both approaches since there was a one-to-one correspondence between the number of data files and log files. Thus, there was no significant difference in this regard.

Ultimately, the only sigificant benefit of using the batch approach was the reduced waiting time. However, given the additional storage requirement and complexities of the batch approach, I decided the drawbacks outweighed the benefits, and decided to use the event-driven approach.

## Bottlenecks ##

After implementing the event-driven approach, I noticed that a bottleneck occurred when traversing through the files to determine the latest timestamp. I also noticed that this same process was significantly slower when run in the Lambda function (via the AWS SDK) as opposed to on the AWS CLI. My hypothesis is that this was afftected by the programming language used to access the SDK since a loop was required when traversing the files. One possibility is to write the same code in another language like Java to see if the performance improves.