function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "query": document.getElementById("ta_query").value,
        "case_sensitive": document.getElementById("ta_case_sensitive").value,
        "max_length_diff": document.getElementById("ta_max_length_diff").value,
        "min_similarity": document.getElementById("ta_min_similarity").value,
        "max_names": document.getElementById("ta_max_names").value,
        "max_aliases": document.getElementById("ta_max_aliases").value,
    };

    fetch("./run_nen", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data["result"];
        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function get_json(){
    query = document.getElementById("ta_query").value;
    case_sensitive = document.getElementById("ta_case_sensitive").value;
    max_length_diff = document.getElementById("ta_max_length_diff").value;
    min_similarity = document.getElementById("ta_min_similarity").value;
    max_names = document.getElementById("ta_max_names").value;
    max_aliases = document.getElementById("ta_max_aliases").value;

    query = encodeURI(query)
    case_sensitive = encodeURI(case_sensitive)
    max_length_diff = encodeURI(max_length_diff)
    min_similarity = encodeURI(min_similarity)
    max_names = encodeURI(max_names)
    max_aliases = encodeURI(max_aliases)

    url = `./query_nen?query=${query}`
    url = `${url}&case_sensitive=${case_sensitive}`
    url = `${url}&max_length_diff=${max_length_diff}`
    url = `${url}&min_similarity=${min_similarity}`
    url = `${url}&max_names=${max_names}`
    url = `${url}&max_aliases=${max_aliases}`

    window.open(url, "_blank");
}
