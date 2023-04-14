function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "type": document.getElementById("sl_type").value,
        "id": document.getElementById("ta_id").value,
    };

    fetch("./run_id_to_name", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data["result"];
        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function get_json(){
    type = document.getElementById("sl_type").value;
    id = document.getElementById("ta_id").value;

    type = encodeURIComponent(type)
    id = encodeURIComponent(id)

    url = `./query_id_to_name?type=${type}&id=${id}`
    window.open(url, "_blank");
}
