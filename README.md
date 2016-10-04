### Bringing you yesterday's database today!

## Aurora Echo

This tool assists in AWS RDS Aurora database lifecycle management. It is a companion project to [RDS Echo](https://github.com/blacklocus/rds-echo), which deals solely in non-Aurora instances.

### What do?
Use this tool to automatically restore an Aurora database cluster from a snapshot, promote it to live via DNS updates in Route53, and at EOL destroy the managed cluster.

The three different stages here -- new, promote, retire -- can all be used independently of each other and run periodically without regard for timing of the other stages. This is because the lifecycle stages are tracked on the database instances themselves via tags. Each stage run will only operate on a database that is tagged appropriately.

Have multiple development databases? Aurora-Echo allows management of unlimited independent lifecycles; just name them differently in configuration and don't worry about them interfering with each other.

## `new`
- **What**: Create a new cluster and instance restored from a snapshot.
- **How**: Given a cluster name as input, find the latest snapshot of said cluster and use it as a basis for restoring a new cluster.
- **When**: You may want to run this periodically on a cron job. It includes a safety check to make sure it hasn't restored a cluster in the last (configurable) n hours and aborts if a managed cluster is too new.

#### Configuration
- `-a, --aws_account_number [required]`
  - Your AWS account number
- `-r, --region [required]`
  - e.g. `us-east-1`
- `-n, --managed_name [required]`
  - The name of the cluster and instance you want to create/restore to. This will also go into the tag to track managed instances. i.e. `development`
- `-s, --cluster_snapshot_name [required]`
  - The cluster name of the snapshot you want to restore from, i.e. `production`
- `-sub, --db_subnet_group_name [required]`
  - VPC subnet group to restore into
- `-c, --db_instance_class [required]`
  - Size of the database instance to create, e.g. `db.r3.2xlarge`
- `-e, --engine`
  - Defaults to `aurora`
- `-az, --availability_zone`
  - e.g. `us-east-1c`. If not set, AWS defaults this to the region the parent snapshot is in.
- `-sg, --vpc_security_group_id`
  - Allows multiple inputs (use one option flag per input).
  - The ID of any security groups to assign to the created instance/cluster
- `-t, --tag`
  - Allows multiple inputs (use one option flag per input).
  - Any custom tags to assign to the cluster and instance along with the managed tags automatically assigned by aurora-echo, e.g. `purple=true`
- `-h, --minimum_age_hours`
  - If an existing managed instance has been created within the last `-h` hours, abort creation of a new instance. Defaults to 20.
- `--help`
  - Show options and exit.

## `promote`
- **What**: Promote a database instance from `new` to `promoted` by updating a record set's DNS entry in Route53 to point to the newly promoted database's endpoint.
- **How**: Look for an instance in RDS that is in the stage `new`, and update the supplied record set's DNS entry to its endpoint. Move any appropriate existing instance's stage from `promoted` to `retired`, and update this instance's stage from `new` to `promoted`.
- **When**: You may want to run this periodically on a cron job. It will only operate when an instance is in the `new` stage and has status `available`.

#### Configuration
- `-a, --aws_account_number [required]`
  - Your AWS account number
- `-r, --region [required]`
  - e.g. `us-east-1`
- `-n, --managed_name [required]`
  - The managed name tracking the instance you want to promote. This is the same a the `-managed_name` parameter used in the `new` step.
- `-z, --hosted_zone_id [required]`
  - The ID of the hosted zone containing the DNS record set to be updated
- `-rs, --record_set [required]`
  - Name of the record set to update, e.g. `dev-db.mycompany.com`. aurora-echo only supports CNAME updates.
- `--ttl`
  - TTL in seconds. Defaults to 60.
- `--help`
  - Show options and exit.


## `retire` TODO
- **What**: Create a new cluster and instance restored from a snapshot.
- **How**: Given a cluster name as input, find the latest snapshot of said cluster and use it as a basis for restoring a new cluster.
- **When**: You may want to run this periodically on a cron job. It includes a safety check to make sure it hasn't restored a cluster in the last (configurable) n hours and aborts if a managed cluster is too new.

