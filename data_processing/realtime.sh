#! /bin/bash

start="None"
end="None"
overwrite=0

if [ "$#" == 0 ]; then
  echo "No Arguments Provided"
  exit 1
fi

while [ "$#" -gt 1 ]; do
  case $1 in
    -s | --start )      shift
                        start=$1
                        ;;
    -e | --end )        shift
                        end=$1
                        ;;
    -o | --overwrite )  overwrite=1
                        ;;
    * )                 echo "Invalid Option(s)"
                        exit 1
                        ;;
    esac
    shift
done

directory=$1

if [ $overwrite == "0" ]; then
  if [ -d $directory ]; then
    echo "Directory Already Exists"
    exit 1
  fi
fi

python3 throughflow.py $start $end $directory

python3 adcp_vectors.py $start $end $directory

python3 adcp_sections.py $start $end $directory

exit 0
