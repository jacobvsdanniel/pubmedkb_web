function run_query(){
    document.getElementById("div_status").innerHTML = "Loading...";

    request_data = {
        "type": document.getElementById("sl_type").value,
        "gene_id": document.getElementById("ta_gene_id").value,
        "variant_id": document.getElementById("ta_variant_id").value,
        "disease_id": document.getElementById("ta_disease_id").value,
    };

    fetch("./run_gvd_stats", {method: "post", body: JSON.stringify(request_data)})
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
    gene_id = document.getElementById("ta_gene_id").value;
    variant_id = document.getElementById("ta_variant_id").value;
    disease_id = document.getElementById("ta_disease_id").value;

    type = encodeURIComponent(type)
    gene_id = encodeURIComponent(gene_id)
    variant_id = encodeURIComponent(variant_id)
    disease_id = encodeURIComponent(disease_id)

    url = `./query_gvd_stats`
    url = `${url}?type=${type}`
    url = `${url}&gene_id=${gene_id}`
    url = `${url}&variant_id=${variant_id}`
    url = `${url}&disease_id=${disease_id}`

    window.open(url, "_blank");
}
