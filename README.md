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

3. Use a sentinel file to signal the end of the upload, and trigger the ETL process using this file. This would have been easy to implement, but if the upload crashed before the sentinel file was uploaded, the ETL process would never be triggered. Including a sentinel file in *conjunction* with one of the above approaches would have been a good idea to guarantee the completion of the upload. However, I did not have control over how the files were uploaded, so this was not implemented.

### Comparison ###

Since the third approach could not be implemented, I compared the tradeoffs between the first two approaches:

* The primary difference between these approaches was that the first was event-driven while the second was a batch job.
* The benefit of the event-driven approach was that additional storage was not required for the storage of log files and it was simple to implement. However, the drawback was that there would be more waiting time while files were uploading.
* The batch approach would, on average, incur less waiting time since it would only run once per day. However, it required allocating additional S3 storage for the log files. Additionally, this approach introduced other complexities, such as: what if multiple batches were uploaded on the same day? We would then need to keep track of all the batches uploaded that day. The likelihood for errors would be higher in this approach because of these complexities.
* The number of files that needed to be examined was similar in both approaches since there was a one-to-one correspondence between the number of data files and log files. Thus, there was no significant difference in this regard.

Ultimately, the only sigificant benefit of using the batch approach was the reduced waiting time. However, given the additional storage requirement and complexities of the batch approach, I decided the drawbacks outweighed the benefits, and decided to use the event-driven approach.

## Step Function ##

![Step Function](https://user-images.githubusercontent.com/40527812/61487866-b973c180-a95b-11e9-8364-2e49337a4ee0.png)

This was the step function that orchestrated the workflow of the event-driven approach described above. Here were the steps that occurred when the step function was invoked:

1. The step function was triggered using the first file that was uploaded in a flight.
2. Control was passed to the "Traverse & Count Files" function. This function traversed all of the files for that particular flight and determined what the latest timestamp was. It also counted the number of files in each image type (since different types of images were collected per flight), which would be used later in the step function. Finally, the function checked if the latest timestamp was over a predetermined number of hours ago (say, 5 hours). If so, it assumed that the file upload was complete and returned a success. Otherwise, it returned a failure. The success/failure result and the file counts were passed on to the rest of the step function.
3. Control was passed to the "Check Upload Complete" function. This function checked the success/failure result from the "Traverse & Count Files" function.
    * If a success result was returned, control was passed to the parallel component ("GPS File Exists", "O File Exists", "I File Exists") to check whether the necessary files existed. If all files existed, control was passed to the "Populate Database" function (described below). Otherwise, the step function failed.
    * If a failure result was returned, control was passed to the "Wait for Upload" function. This function invoked a delay of a predetermined amount of time (say, 5 hours) to allow the files more time to upload. After the delay, control was passed to the "Traverse & Count Files" function to check the files again.
4. There was a maximum limit for how many times the "Wait For Upload" function would be called, to prevent an infinite loop. If this limit was exceeded, the "Check Upload Complete" function would pass control to the "Retries Exceeded" function and the step function would fail.
5. The "Populate Database" function would be executed if all previous steps were successful. This function parsed the data and populated it into the MySQL database. In addition, it compared the file counts from the "Traverse & Count Files" function with the GPS readings to verify that the number of different image files were consistent with the duration of flight. Since the GPS readings were not parsed until the "Populate Database" function, the file counts could not be checked until this step. Hence, the file counts must be passed from the "Traverse & Count Files" function all the way to the "Populate Database" function.

## Bottlenecks ##

After implementing the event-driven approach, I noticed that a bottleneck occurred when traversing through the files to determine the latest timestamp. I also noticed that this same process was significantly slower when run in the Lambda function (via the AWS SDK) as opposed to on the AWS CLI. My hypothesis is that this was afftected by the programming language used to access the SDK since a loop was required when traversing the files. One possibility is to write the same code in another language like Java to see if the performance improves.

## Links ##
[Slides](bit.ly/agrview-slides)
[Presentation](https://youtu.be/jUZb01HzHuA)