import boto3
import io

class S3_Bucket():
    def __init__(self, bucket_name):
        self.s3 = boto3.client('s3')
        self.s3_resource = boto3.resource('s3')
        self.bucket_name = bucket_name
    def get_s3_file_bytes(self, key):
        obj = self.s3.get_object(Bucket=self.bucket_name, Key=key)
        return io.BytesIO(obj['Body'].read())
    def write_pickle(self, df, key):
        pickle_buffer = io.BytesIO()
        df.to_pickle(pickle_buffer)
        self.s3_resource.Object(self.bucket_name, key).put(Body=pickle_buffer.getvalue())
        print(f'wrote {key} to bucket {self.bucket_name}')