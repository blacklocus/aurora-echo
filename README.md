
## Aurora Echo

### Bringing you yesterday's database today!
This tool assists in AWS RDS Aurora database lifecycle management. It is a companion project to [RDS Echo](https://github.com/blacklocus/rds-echo), which deals solely in non-Aurora instances.

### What do?
Use this tool to automatically restore an Aurora database cluster from a snapshot, promote it to live via DNS updates in Route53, and at EOL destroy the managed cluster.

The five different stages here -- new, clone, modify, promote, retire -- can all be run periodically without regard for timing of the other stages. This is because the commands are idempotent and the lifecycle stages are tracked on the database instances themselves via tags. Thus each command will only operate on a database that is tagged appropriately, and will exit cleanly if there is no database in the appropriate stage.

Have multiple development databases? Aurora Echo allows management of unlimited independent lifecycles; just name them differently in configuration and don't worry about them interfering with each other.

## Stages
This is our story: On a regular basis, restore the latest production snapshot to a new development instance, promote that instance to replace its former self, and then destroy the old instance.

Each `aurora-echo` command progresses a managed instance through a series of stages:

  - (non-existent) --`aurora-echo new` | `aurora-echo clone`-->     **new**
  - **new**   --`aurora-echo modify`--> **modified**
  - **modified**   --`aurora-echo promote`--> **promoted**
    - This also results in any previously **promoted** instance advancing to **retired**
  - **retired**  --`aurora-echo retire`-->  (non-existent)

So in the straightforward case, each command is run in succession after the previous commands stabilize and leave the DB instance in the "available" state.

All state tracking metadata is stored as AWS resource tags on the cluster and instance.


## Installation
Aurora Echo is a command-line tool that uses [Boto](https://github.com/boto/boto3). It has been tested on Ubuntu 14.04 with Python 3.4.3.

You will need to set up AWS auth as per the [boto documentation](https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration).

Grab the latest version and set it to executable like so:
```sh
sudo curl -o /usr/local/bin/aurora-echo -L "https://github.com/blacklocus/aurora-echo/releases/download/v2.0.1/aurora-echo" && \
sudo chmod +x /usr/local/bin/aurora-echo
```

## Usage

### `new`
- **What**: Create a new cluster and instance restored from a snapshot.
- **How**: Given a cluster name as input, find the latest snapshot of said cluster and use it as a basis for restoring a new cluster.
- **When**: You may want to run this periodically on a cron job. It includes a safety check to make sure it hasn't restored a cluster in the last (configurable) n hours and aborts if a managed cluster is too new.
- **State**: Leaves the db in the `new` state

#### Configuration
- `-a, --aws-account-number [required]`
  - Your AWS account number
- `-r, --region [required]`
  - e.g. `us-east-1`
- `-n, --managed-name [required]`
  - The name of the cluster and instance you want to create/restore to. This will also go into the tag to track managed instances. e.g. `development`
- `-s, --cluster-snapshot-name [required]`
  - The cluster name of the snapshot you want to restore from, e.g. `production`
- `-sub, --db-subnet-group-name [required]`
  - VPC subnet group to restore into
- `-c, --db-instance-class [required]`
  - Size of the database instance to create, e.g. `db.r3.2xlarge`
- `-e, --engine`
  - Defaults to `aurora`
- `-az, --availability-zone`
  - e.g. `us-east-1c`. If not set, AWS defaults this to the region the parent snapshot is in.
- `-sg, --vpc-security-group-id`
  - The ID of any security groups to assign to the created instance/cluster
  - Allows multiple inputs (use one option flag per input).
- `-t, --tag`
  - Any custom tags to assign to the cluster and instance, e.g. `purple=true`
  - Custom tags will not interfere with, nor should include the Aurora Echo management tags
  - Allows multiple inputs (use one option flag per input).
- `-h, --minimum-age-hours`
  - If an existing managed instance has been created within the last `-h` hours, abort creation of a new instance. Defaults to 20.
- `-i, --interactive`
  - Prompt the user for confirmation before making changes. Defaults to true.
- `-sf, --suffix`
  - An optional suffix to append to the name of new clusters and db instances.
- `--help`
  - Show options and exit.


### `clone`
- **What**: Create a new cluster and instance that is a clone of an existing database. See [AWS docs on cloning](http://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Aurora.Managing.Clone.html) for more information.
- **How**: Given a cluster name as input, use the [restore_db_cluster_to_point_in_time](http://boto3.readthedocs.io/en/latest/reference/services/rds.html#RDS.Client.restore_db_cluster_to_point_in_time) method with `RestoreType=copy-on-write` to create it as a clone. The `RestoreType=full-copy` is not supported by aurora-echo right now. Use `new` to simulate that.
- **When**: You may want to run this periodically on a cron job. It includes a safety check to make sure it hasn't restored a cluster in the last (configurable) n hours and aborts if a managed cluster is too new.
- **State**: Leaves the db in the `new` state

#### Configuration
- `-a, --aws-account-number [required]`
  - Your AWS account number
- `-r, --region [required]`
  - e.g. `us-east-1`
- `-n, --managed-name [required]`
  - The name of the cluster and instance you want to create/restore to. This will also go into the tag to track managed instances. e.g. `development`
- `-s, --source-cluster-name [required]`
  - The cluster name to clone, e.g. `production`
- `-sub, --db-subnet-group-name [required]`
  - VPC subnet group to restore into
- `-c, --db-instance-class [required]`
  - Size of the database instance to create, e.g. `db.r3.2xlarge`
- `-e, --engine`
  - Defaults to `aurora`
- `-az, --availability-zone`
  - e.g. `us-east-1c`. If not set, AWS defaults this to the region the parent snapshot is in.
- `-sg, --vpc-security-group-id`
  - The ID of any security groups to assign to the created instance/cluster
  - Allows multiple inputs (use one option flag per input).
- `-t, --tag`
  - Any custom tags to assign to the cluster and instance, e.g. `purple=true`
  - Custom tags will not interfere with, nor should include the Aurora Echo management tags
  - Allows multiple inputs (use one option flag per input).
- `-h, --minimum-age-hours`
  - If an existing managed instance has been created within the last `-h` hours, abort creation of a new instance. Defaults to 20.
- `-pgn, --db-parameter-group-name'`
  - The database parameter group name to use, e.g. 'custom.aurora5.7'
- `-i, --interactive`
  - Prompt the user for confirmation before making changes. Defaults to true.
- `-sf, --suffix`
  - An optional suffix to append to the name of new clusters and db instances.
- `--help`
  - Show options and exit.


### `modify`
- **What**: Progress a database instance from `new` to `modified` by optionally adding an IAM role. In order to prevent a branching state diagram, all lifecycles must pass through this stage. If no IAM role need be applied, simply leave off the optional parameter and the state will be progressed without actually changing the cluster or instance.
- **How**: Look for a managed instance in RDS that is in the stage `new`. Apply the provided IAM role to it, if any. This stage could be expanded in order to modify other attributes not available via API on creation.
- **When**: You may want to run this periodically on a cron job. It will only operate when an instance is in the `new` stage and its cluster has status `available`.
- **State**: Leaves the new db in the `modified` state

#### Configuration
- `-a, --aws-account-number [required]`
  - Your AWS account number
- `-r, --region [required]`
  - e.g. `us-east-1`
- `-n, --managed-name [required]`
  - The managed name tracking the instance you want to promote. This is the same as the `--managed-name` parameter used in the `new` step.
- ` -iam, --iam-role-name`
  - The name of the IAM role. This will be converted to an ARN in order to apply it to the cluster.
- `-i, --interactive`
  - Prompt the user for confirmation before making changes. Defaults to true.
- `--help`
  - Show options and exit.


### `promote`
- **What**: Progress a database instance from `modified` to `promoted` by updating a record set's DNS entry in Route53 to point to the newly promoted database's endpoint.
- **How**: Look for a managed instance in RDS that is in the stage `modified`, and update the supplied record set's DNS entry to its endpoint. Move any appropriate existing instance's stage from `promoted` to `retired`, and update this instance's stage from `modified` to `promoted`.
- **When**: You may want to run this periodically on a cron job. It will only operate when an instance is in the `modified` stage and has status `available`.
- **State**: Leaves the new db in the `promoted` state
- **State**: Leaves the previously promoted db in the `retired` state

#### Configuration
- `-a, --aws-account-number [required]`
  - Your AWS account number
- `-r, --region [required]`
  - e.g. `us-east-1`
- `-n, --managed-name [required]`
  - The managed name tracking the instance you want to promote. This is the same as the `--managed-name` parameter used in the `new` step.
- `-z, --hosted-zone-id [required]`
  - The ID of the hosted zone containing the DNS record set to be updated. You can give this option multiple times to add the same record set in multiple hosted zones.
- `-rs, --record-set [required]`
  - Name of the record set to update, e.g. `dev-db.mycompany.com`. Aurora Echo only supports CNAME updates.
- `--ttl`
  - TTL in seconds. Defaults to 60.
- `-i, --interactive`
  - Prompt the user for confirmation before making changes. Defaults to true.
- `--help`
  - Show options and exit.


### `retire`
- **What**: Delete a managed instance and cluster that is in the `retired` stage.
- **How**: Look for a managed instance in RDS that is in the stage `retired` and delete the instance and its containing cluster. There is no option to make a final snapshot. All automated instance/cluster snapshots **will be deleted**.
- **When**: You may want to run this periodically on a cron job. It will only operate when a managed instance is in the `retired` stage.
- **State**: Leaves the db in a non-existent state

#### Configuration
- `-a, --aws-account-number [required]`
  - Your AWS account number
- `-r, --region [required]`
  - e.g. `us-east-1`
- `-n, --managed-name [required]`
  - The managed name tracking the instance you want to retire. This is the same as the `--managed-name` parameter used in previous steps.
- `-i, --interactive`
  - Prompt the user for confirmation before making changes. Defaults to true.
- `--help`
  - Show options and exit.


## Notes!
- This tool creates instances and clusters with today's date attached, such as `development-2016-10-05`. This combined with the previous-instance freshness check will prevent multiple instances from being created in a cluster.
- The boto_monkey and eggsecute packaging helpers came from [this project](https://github.com/rholder/dynq)

## Development
A binary is provided (see Installation); however, to build your own from source, run `make all`. You will need to have [virtualenv](https://virtualenv.pypa.io/en/stable/) installed.
