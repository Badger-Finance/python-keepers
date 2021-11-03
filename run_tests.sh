#!/bin/bash

declare -a eth_tests=(
    "test_general_harvester"
    "test_oracle"
    "test_rebase"
    "test_rebalance"
    "test_ibbtc_fee_collect"
    )

declare -a arb_tests=(
    "test_arbitrum_earner"
    "test_arbitrum_harvester"
    )

failing_tests="failures:"
passing_tests="passed:"

for i in "${eth_tests[@]}"
do
    if brownie test tests/"$i".py --network=hardhat-fork; then
        passing_tests="$passing_tests $i"
        continue
    else
        failing_tests="$failing_tests $i"
    fi
done

if [ "$failing_tests" != "failures:" ]; then
    echo "$failing_tests"
    echo "$passing_tests"
    exit 1
else
    echo "ETH TESTS PASSED"
fi

# for i in "${arb_tests[@]}"
# do
#     brownie test tests/"$i".py --network=hardhat-arbitrum-fork
#     if [ $? != 0 ]; then
#         break
#     else
#         continue
#     fi
# done
