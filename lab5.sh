sudo yum install -y httpd-tools

export URL="http://mikosins-workshop-872025814.eu-central-1.elb.amazonaws.com"
for i in {1..60}; do ab -n 100 -c 2 $URL; sleep 1; done
