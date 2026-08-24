package storage

import (
	"context"
	"errors"
	"io"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	awsconfig "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

var ErrObjectTooLarge = errors.New("object exceeds read limit")

type ObjectInfo struct {
	Size        int64
	ContentType string
}
type Store interface {
	PresignUpload(context.Context, string, string, time.Duration) (string, error)
	PresignDownload(context.Context, string, time.Duration) (string, error)
	Head(context.Context, string) (ObjectInfo, error)
	Read(context.Context, string, int64) ([]byte, ObjectInfo, error)
}

type S3Store struct {
	client  *s3.Client
	presign *s3.PresignClient
	bucket  string
}

func NewS3Store(ctx context.Context, endpoint, presignEndpoint, region, bucket, accessKey, secretKey string, pathStyle bool) (*S3Store, error) {
	cfg, err := awsconfig.LoadDefaultConfig(ctx, awsconfig.WithRegion(region), awsconfig.WithCredentialsProvider(aws.CredentialsProviderFunc(func(context.Context) (aws.Credentials, error) {
		return aws.Credentials{AccessKeyID: accessKey, SecretAccessKey: secretKey}, nil
	})))
	if err != nil {
		return nil, err
	}
	client := s3.NewFromConfig(cfg, func(o *s3.Options) { o.BaseEndpoint = aws.String(endpoint); o.UsePathStyle = pathStyle })
	presignClient := s3.NewFromConfig(cfg, func(o *s3.Options) { o.BaseEndpoint = aws.String(presignEndpoint); o.UsePathStyle = pathStyle })
	return &S3Store{client: client, presign: s3.NewPresignClient(presignClient), bucket: bucket}, nil
}
func (s *S3Store) PresignUpload(ctx context.Context, key, contentType string, ttl time.Duration) (string, error) {
	// Browsers cannot set Content-Length, so validate the exact size during completion instead.
	r, err := s.presign.PresignPutObject(ctx, &s3.PutObjectInput{Bucket: aws.String(s.bucket), Key: aws.String(key), ContentType: aws.String(contentType)}, s3.WithPresignExpires(ttl))
	if err != nil {
		return "", err
	}
	return r.URL, nil
}
func (s *S3Store) PresignDownload(ctx context.Context, key string, ttl time.Duration) (string, error) {
	r, err := s.presign.PresignGetObject(ctx, &s3.GetObjectInput{Bucket: aws.String(s.bucket), Key: aws.String(key)}, s3.WithPresignExpires(ttl))
	if err != nil {
		return "", err
	}
	return r.URL, nil
}
func (s *S3Store) Head(ctx context.Context, key string) (ObjectInfo, error) {
	r, err := s.client.HeadObject(ctx, &s3.HeadObjectInput{Bucket: aws.String(s.bucket), Key: aws.String(key)})
	if err != nil {
		return ObjectInfo{}, err
	}
	return ObjectInfo{Size: aws.ToInt64(r.ContentLength), ContentType: aws.ToString(r.ContentType)}, nil
}
func (s *S3Store) Read(ctx context.Context, key string, maxBytes int64) ([]byte, ObjectInfo, error) {
	if maxBytes <= 0 {
		return nil, ObjectInfo{}, ErrObjectTooLarge
	}
	r, err := s.client.GetObject(ctx, &s3.GetObjectInput{Bucket: aws.String(s.bucket), Key: aws.String(key)})
	if err != nil {
		return nil, ObjectInfo{}, err
	}
	defer r.Body.Close()
	if r.ContentLength != nil && *r.ContentLength > maxBytes {
		return nil, ObjectInfo{}, ErrObjectTooLarge
	}
	data, err := io.ReadAll(io.LimitReader(r.Body, maxBytes+1))
	if err != nil {
		return nil, ObjectInfo{}, err
	}
	if int64(len(data)) > maxBytes {
		return nil, ObjectInfo{}, ErrObjectTooLarge
	}
	return data, ObjectInfo{Size: int64(len(data)), ContentType: aws.ToString(r.ContentType)}, nil
}
